#!/bin/bash
# ─────────────────────────────────────────────────────────────────────
# run_spark.sh – Submit PySpark Structured Streaming Job
# Phải chạy bên TRONG container spark-master
#
# Cách chạy từ máy host:
#   docker exec -it spark-master bash /app/run_spark.sh
# ─────────────────────────────────────────────────────────────────────

# ─── Thiết lập PATH (cần thiết khi gọi qua docker exec) ──────────────
export SPARK_HOME="/opt/spark"
export PATH="$SPARK_HOME/bin:$SPARK_HOME/sbin:$PATH"
export PYSPARK_PYTHON=python3

# ─── Lấy phiên bản Spark và Scala đang chạy ──────────────────────────
SPARK_VERSION=$(python3 -c "import pyspark; print(pyspark.__version__)" 2>/dev/null || echo "4.1.2")
SCALA_VERSION=$(ls /opt/spark/jars/scala-library-*.jar 2>/dev/null | sed 's/.*scala-library-\([0-9]*\.[0-9]*\).*/\1/' | head -1)

# Spark 4.x dùng Scala 2.13, Spark 3.x dùng Scala 2.12
if [ -z "$SCALA_VERSION" ]; then
    SCALA_VERSION="2.13"
fi

echo "Phát hiện: Spark ${SPARK_VERSION}, Scala ${SCALA_VERSION}"

# ─── Packages (tự động tải JAR đúng phiên bản) ───────────────────────
PACKAGES="org.apache.spark:spark-sql-kafka-0-10_${SCALA_VERSION}:${SPARK_VERSION},\
org.postgresql:postgresql:42.7.3"

# ─── Maven repository cache ───────────────────────────────────────────
IVY_DIR="/app/.ivy2"
mkdir -p "$IVY_DIR"

# ─── Submit job ───────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Đang submit Spark Streaming Job..."
echo "  Packages: $PACKAGES"
echo "============================================================"

/opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --driver-memory  2g \
    --executor-memory 2g \
    --executor-cores  2 \
    --packages "$PACKAGES" \
    --conf "spark.jars.ivy=$IVY_DIR" \
    --conf "spark.driver.extraJavaOptions=-Divy.home=$IVY_DIR" \
    --py-files /app/dls_ts_net.py \
    /app/main.py
