import json
import time
import random
import socket
from datetime import datetime
from kafka import KafkaProducer

# Kafka broker in Docker network
KAFKA_BROKER = 'kafka:9092'
TOPIC_NAME = 'stock-updates'

# Wait for Kafka broker to be ready
def wait_for_kafka(host, port, timeout=60):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=5):
                print(f"✅ Kafka is available at {host}:{port}")
                return
        except OSError:
            print(f"⏳ Waiting for Kafka at {host}:{port}...")
            time.sleep(2)
    raise TimeoutError(f"❌ Kafka not available after {timeout} seconds")

wait_for_kafka('kafka', 9092)

# Initialize Kafka producer
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Sample stock symbols
symbols = [
    'AAPL', 'GOOG', 'MSFT', 'TSLA', 'AMZN', 'FB', 'NFLX', 'NVDA', 'BRK.A', 'V',
    'JPM', 'UNH', 'HD', 'PG', 'DIS', 'VZ', 'INTC', 'CMCSA', 'PEP', 'KO', 'SCHD',
    'JEPI', 'DGRO'
]

print(f"🚀 Producing messages to topic '{TOPIC_NAME}'... Press CTRL+C to stop.")
try:
    while True:
        stock_data = {
            'symbol': random.choice(symbols),
            'price': round(random.uniform(100, 1500), 2),
            'timestamp': datetime.utcnow().isoformat()
        }
        producer.send(TOPIC_NAME, value=stock_data)
        print(f"Sent: {stock_data}")
        time.sleep(1)
except KeyboardInterrupt:
    print("🛑 Stopped producing.")

producer.flush()

