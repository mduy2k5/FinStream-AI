from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

# Cấu hình các tham số mặc định cho DAG
default_args = {
    'owner': 'admin',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=2),
}

# Định nghĩa DAG
with DAG(
    'stock_ingestion_yfinance',
    default_args=default_args,
    description='DAG cào dữ liệu từ Yahoo Finance và đẩy vào Kafka Broker hàng ngày',
    schedule_interval='0 17 * * 1-5',  # Chạy vào lúc 17:00 từ Thứ 2 đến Thứ 6 hàng tuần (giờ đóng cửa sàn chứng khoán)
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['stock', 'ingestion', 'yfinance'],
) as dag:

    # Task cào dữ liệu phiên gần nhất và đẩy lên Kafka
    ingest_stock_data = BashOperator(
        task_id='fetch_and_produce_yfinance',
        bash_command='python /opt/airflow/producer/yfinance_producer.py --mode latest',
        env={
            'KAFKA_BROKER': 'kafka:9092'  # Kết nối tới Broker nội bộ trong Docker network
        }
    )

    ingest_stock_data
