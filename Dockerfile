FROM python:3.9

RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		postgresql \
		postgresql-client \
	&& rm -rf /var/lib/apt/lists/*



WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install -r requirements.txt
RUN mkdir -p /data/media /data/static
RUN ln -s /data/media
RUN ln -s /data/static
COPY . .
EXPOSE 8000
CMD ['gunicorn', 'dnaorder.wsgi:application', '--bind', '0.0.0.0:8000']
# CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
