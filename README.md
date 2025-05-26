# Realtime Stock-Pipeline &nbsp;[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) [![Docker Hub](https://img.shields.io/badge/Docker-ready-lightgrey?logo=docker)](https://docs.docker.com/)
**Kafka × Spark Structured Streaming × Delta Lake × PostgreSQL × AWS CloudWatch**

![Architecture diagram](realtime_data_flow)

> A fully-containerised data pipeline that ingests live market prices, enriches them in Spark, persists them in Delta Lake **and** PostgreSQL, and raises CloudWatch alerts when intraday price movements break configured thresholds.

---

## ️🚀 Quick-start

```bash
# 1. Clone and switch into the repo
git clone https://github.com/<you>/realtime-stock-pipeline.git
cd realtime-stock-pipeline

# 2. Create an .env with your AWS creds (NEVER commit this!)
cat <<EOF > .env
AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXX
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_REGION=us-east-2
EOF

# 3. Spin everything up
docker compose up --build     # ^C to stop
docker compose down -v        # tear-down & clear volumes
```
The first start downloads all images, builds the stock_producer container and creates the Delta Lake & Postgres volumes. Subsequent starts are instant.

---

```mermaid
## 🗺️ End-to-end flow

flowchart LR
    subgraph Produce
        P1[stock_producer.py] -->|JSON©| K[Kafka<br/>topic: stock-updates]
    end

    subgraph Transform & Store
        K --> S(Spark Streaming<br/>stock_streaming_with_alerts.py)
        S -->|Delta parquet| D[Delta Lake<br/>/tmp/delta]
        S -->|INSERT| PG[(PostgreSQL)]
        S -->|PutMetricData| CW[(AWS CloudWatch<br/>Custom metric)]
        S -->|PutLogEvents| LOGS[(CloudWatch Logs)]
    end

    style P1 fill:#ffd,stroke:#333
    style K  fill:#f7f7ff,stroke:#333
    style S  fill:#cce,stroke:#333
    style D  fill:#e0ffe0,stroke:#333
    style PG fill:#ffe0e0,stroke:#333
    style CW fill:#e0f0ff,stroke:#333
    style LOGS fill:#e0f0ff,stroke:#333
```

---

## 🧩 Component glossary

| Container           | Image / Code                                                   | Purpose                                                                                                   |
| ------------------- | -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **zookeeper**       | `cp-zookeeper:7.3`                                             | Metadata quorum for Kafka                                                                                 |
| **kafka**           | `cp-kafka:7.3`                                                 | Event backbone – topic **`stock-updates`**                                                                |
| **stock\_producer** | `Dockerfile.producer` + `producer/*.py`                        | Pulls live prices (or mocks) & pushes JSON messages to Kafka                                              |
| **spark**           | `bitnami/spark:3.4.1` + `spark/stock_streaming_with_alerts.py` | Reads Kafka → calculates deltas → writes **Delta Lake** on local disk, forwards CloudWatch metrics & logs |
| **postgres**        | `postgres:13`                                                  | Relational sink (optional: run `delta_to_postgres.py` to load historic data)                              |

---

## 📂 Repository layout

```
.
├─ docker-compose.yml
├─ Dockerfile.producer
├─ producer/
│  ├─ stock_producer.py
│  └─ requirements.txt
├─ spark/
│  ├─ stock_streaming_with_alerts.py   ←  **current streaming job**
│  ├─ stock_streaming.py               ←  _legacy; kept for reference_
│  └─ ...
├─ delta_to_postgres.py
└─ misc / diagrams / notes
```

---

## 📂 Repo layout & "unused" files

Files currently not used in the live stack
| Path                        | Why it exists                                                                                                                                                         |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `spark/stock_streaming.py`  | Initial prototype before alerting & CloudWatch integration were merged into `stock_streaming_with_alerts.py`. Safe to delete once you no longer need the example.     |
| `compare_stock_movement.py` | Stand-alone tester for relative-move logic; replaced by inline UDFs in the streaming job.                                                                             |
| `kafka/init-topic.sh`       | Convenience script for creating the topic manually; the producer now auto-creates topics.                                                                             |
| `AWSCLIV2.pkg`              | Local installer that **is not required** inside Docker; left here only if you need to install the AWS CLI on macOS. Delete it to avoid pushing a 40 MB binary to Git. |
| `realtime_data_flow` image  | Optional architecture PNG used in the README badge. Remove if you host diagrams elsewhere.                                                                            |

---

## ⚙️ Configuration

| Variable                | Location                               | Default     | Description                                                     |
| ----------------------- | -------------------------------------- | ----------- | --------------------------------------------------------------- |
| `PRICE_MOVE_PCT`        | `spark/stock_streaming_with_alerts.py` | `2`         | %-threshold that triggers a CloudWatch alert.                   |
| `AWS_ACCESS_KEY_ID`     | `.env / shell env`                     | —           | IAM user or STS key (CloudWatch → PutMetricData, PutLogEvents). |
| `AWS_SECRET_ACCESS_KEY` | `.env / shell env`                     | —           | Corresponding secret.                                           |
| `AWS_REGION`            | `.env / compose`                       | `us-east-2` | Region for logs & metrics.                                      |

---

## 🔍 Observability & testing

### 1.) Tail Kafka quickly

```bash
docker exec -it $(docker compose ps -q kafka) \
  kafka-console-consumer --bootstrap-server kafka:9092 \
  --topic stock-updates --from-beginning --max-messages 5
```

### 2.) Spark UI

Visit http://localhost:4040 while the Spark container is running to inspect DAGs, streaming progress, executors, etc.

### 3.) CloudWatch

Logs ➜ Log groups ➜ /realtime-stock/alerts – view every alert payload.
Metrics ➜ All metrics ➜ Custom › RealtimeStock – inspect PriceMovePct.
Dashboards – the JSON snippets in README show you how to pin live widgets.

---

## ⌨️ Common commands

| Goal                  | Command                        |
| --------------------- | ------------------------------ |
| start pipeline        | `docker compose up --build`    |
| stop & wipe volumes   | `docker compose down -v`       |
| restart Spark only    | `docker compose restart spark` |
| prune dangling images | `docker image prune -f`        |

---

## 📈 Extending the pipeline ideas

S3 ↔ Delta Lake – mount an S3 bucket & switch the checkpoint / Delta path to s3a://... (with proper IAM perms and --packages io.delta:delta-storage-s3_2.12:...).
Athena or Redshift – crawl the Delta table with Glue or auto-load into Redshift Serverless.
SNS / Slack / Teams alerts – change put_metric_data() to also publish to SNS.
Airflow – wrap the producer + Spark job as DAG tasks for orchestration.

---

## 🛡️ Security notes

IAM policy least privilege: logs:CreateLogGroup, logs:CreateLogStream, logs:PutLogEvents, cloudwatch:PutMetricData.
Never commit .env or any secret file. .gitignore already covers it.
If you publish the repo, consider removing AWSCLIV2.pkg, .DS_Store and other local artefacts to keep image size & clone time small.

---

## ✒️ Author

**Derek Acevedo** – [GitHub](https://github.com/poloman2308) | [Linkedin](https://linkedin.com/in/derekacevedo86)

```pgsql
**Where to put the diagram image?**

* The Mermaid code block above renders natively on GitHub (no PNG required).  
* If you prefer a static PNG, export it from VS Code’s “Mermaid: Preview” and replace the code block with an `![diagram](path/to/png)` reference.

Happy shipping!
```
