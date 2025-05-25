from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StringType, DoubleType, TimestampType

# Define the schema
json_schema = StructType() \
    .add("symbol", StringType()) \
    .add("price", DoubleType()) \
    .add("timestamp", StringType())

# Start SparkSession with Delta support
spark = SparkSession.builder \
    .appName("Stock Stream Processor") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .getOrCreate()

# Read Kafka messages
raw_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "stock-updates") \
    .option("startingOffsets", "latest") \
    .load()

# Parse JSON from Kafka "value" column
parsed_df = raw_df.selectExpr("CAST(value AS STRING) as json_str") \
    .select(from_json(col("json_str"), json_schema).alias("data")) \
    .select("data.*")

# Cast timestamp correctly
final_df = parsed_df.withColumn("timestamp", col("timestamp").cast(TimestampType()))

# Write to Delta
query = final_df.writeStream \
    .format("delta") \
    .outputMode("append") \
    .option("checkpointLocation", "/tmp/delta/stock-checkpoint") \
    .start("/tmp/delta/stock-data")

query.awaitTermination()
