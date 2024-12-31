FROM python:3.11-slim

# Allow statements and log messages to immediately appear in the logs
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

# Install production dependencies.
RUN pip cache purge && pip install --no-cache-dir -r requirements.txt

# Add app to PYTHONPATH
ENV PYTHONPATH=lliza

# Railway server has 8 cpus, so we use 8 workers
# Each worker has 8 threads
# Not sure if this is the best configuration
# timeout 0 is heldover from cloudrun  and I'm not sure if it's necessary still
CMD python lliza/manage.py qcluster & \
exec gunicorn -k uvicorn.workers.UvicornWorker \
--workers 8 --threads 8 --timeout 0 \
--bind :$PORT \
lliza.asgi:application