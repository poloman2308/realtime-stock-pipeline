# spark/stock_streaming_with_alerts.py
# ------------------------------------
"""
Real-time pipeline:
1.  Read JSON messages from Kafka topic `stock-updates`
2.  Parse & type-cast                       -> streaming DataFrame `prices_df`
3.  For each micro-batch:
       • calculate % move vs. previous price per symbol
       • send CloudWatch alert if |move| >= ALERT_THRESHOLD
       • append the batch to Delta Lake table /tmp/delta/stock-data
"""

import os
import json
import time
import boto3
from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import (
    from_json, col, lag, expr, abs as sql_abs, current_timestamp
)
from pyspark.sql.types import StructType, StringType, DoubleType, TimestampType

# ────────────────────────────
# 1. Spark session w/ Delta
# ────────────────────────────
spark = (
    SparkSession.builder
    .appName("Stock Stream Processor + Alerts")
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    .getOrCreate()
)

# ────────────────────────────
# 2. Static config
# ────────────────────────────
ALERT_THRESHOLD = 0.05          # 5 % move
LOG_GROUP       = "stock-movement-alerts"
LOG_STREAM      = "realtime"

# init CloudWatch client *once* on the driver
cw_client = boto3.client("logs", region_name=os.getenv("AWS_REGION", "us-east-1"))

# ensure the destination exists (harmless if it already does)
try:
    cw_client.create_log_group(logGroupName=LOG_GROUP)
except cw_client.exceptions.ResourceAlreadyExistsException:
    pass

try:
    cw_client.create_log_stream(logGroupName=LOG_GROUP, logStreamName=LOG_STREAM)
except cw_client.exceptions.ResourceAlreadyExistsException:
    pass

# ────────────────────────────
# 3. Kafka → streaming DF
# ────────────────────────────
schema = StructType() \
    .add("symbol", StringType()) \
    .add("price",  DoubleType()) \
    .add("timestamp", StringType())       # will cast later

raw_df = (
    spark.readStream.format("kafka")
         .option("kafka.bootstrap.servers", "kafka:9092")
         .option("subscribe", "stock-updates")
         .option("startingOffsets", "latest")
         .load()
)

prices_df = (
    raw_df.select(from_json(col("value").cast("string"), schema).alias("data"))
          .select("data.*")
          .withColumn("timestamp", col("timestamp").cast(TimestampType()))
)

# ────────────────────────────
# 4. foreachBatch alert logic
# ────────────────────────────
def alert_and_write_to_delta(batch_df, batch_id):
    """
    • batch_df  : DataFrame containing a *micro-batch* of new rows
    • batch_id  : long      (we ignore here, but Spark passes it)

    Steps:
      1. find previous price per symbol (within this batch)
         NOTE: because every record is unique in time, previous row in the
               *micro-batch* is previous tick overall.
      2. compute percentage move
      3. filter breaches  |move_pct| >= 5 %
      4. push a log-event per breach to CloudWatch Logs
      5. append the batch to Delta
    """
    # Window to grab previous price inside symbol-partition ordered by timestamp
    w = Window.partitionBy("symbol").orderBy("timestamp")

    enriched = (
        batch_df
        .withColumn("prev_price", lag("price").over(w))
        .withColumn(
            "price_diff_pct",
            (col("price") - col("prev_price")) / col("prev_price")
        )
        .withColumn("ingest_ts", current_timestamp())
    )

    # ------------- 4a send alerts -------------
    alerts = (
        enriched
        .filter(col("prev_price").isNotNull())
        .filter(sql_abs(col("price_diff_pct")) >= ALERT_THRESHOLD)
        .select("symbol", "price", "prev_price", "price_diff_pct", "timestamp")
    )

    # collect to driver (only small sets when alerts occur)
    for row in alerts.collect():
        message = {
            "symbol"   : row.symbol,
            "price"    : row.price,
            "prev"     : row.prev_price,
            "move_pct" : row.price_diff_pct,
            "event_ts" : str(row.timestamp)
        }
        cw_client.put_log_events(
            logGroupName  = LOG_GROUP,
            logStreamName = LOG_STREAM,
            logEvents     = [{
                "timestamp": int(round(time.time() * 1000)),
                "message"  : json.dumps(message)
            }]
        )

    # ------------- 4b persist to Delta -------------
    # We drop helper cols before writing
    (
        enriched.drop("prev_price", "price_diff_pct", "ingest_ts")
        .write.format("delta")
        .mode("append")
        .save("/tmp/delta/stock-data")
    )

# ────────────────────────────
# 5. Start the query
# ────────────────────────────
(
    prices_df.writeStream
    .foreachBatch(alert_and_write_to_delta)
    .option("checkpointLocation", "/tmp/delta/stock-checkpoint")   # same folder is OK
    .start()
    .awaitTermination()
)
