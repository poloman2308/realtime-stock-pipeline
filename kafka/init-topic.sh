#!/bin/bash

docker exec -it realtime-stock-pipeline-kafka-1 kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --replication-factor 1 \
  --partitions 3 \
  --topic stock-updates

echo "Kafka topic 'stock-updates' created."

chmod +x kafka/init-topic.sh

./kafka/init-topic.sh

