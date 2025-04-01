FROM python:3.12.9-slim
ENV MYSQL_HOST=mysql-svc MYSQL_USER=root MYSQL_PASSWORD=root MYSQL_DB=translations
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./app /code
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]