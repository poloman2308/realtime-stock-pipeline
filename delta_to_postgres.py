from pyspark.sql import SparkSession

# Spark session with Delta enabled
spark = SparkSession.builder \
    .appName("DeltaToPostgres") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .getOrCreate()

# 🔄 Read from Delta (Bronze)
df = spark.read.format("delta").load("/tmp/delta/bronze_stock_data")

# Optional: Filter latest records or clean data
df_clean = df.dropna()

# 💾 Write to PostgreSQL (Silver)
df_clean.write \
    .format("jdbc") \
    .option("url", "jdbc:postgresql://localhost:5433/stock_data") \
    .option("dbtable", "public.stock_prices") \
    .option("user", "postgres") \
    .option("password", "postgres") \
    .option("driver", "org.postgresql.Driver") \
    .mode("overwrite") \
    .save()

print("✅ Exported stock data to PostgreSQL!")
