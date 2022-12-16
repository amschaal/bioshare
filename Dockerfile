FROM python:3.9

RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		postgresql \
		postgresql-client \
		openssh-server \
		rsync \
	&& rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1234 bioshare
RUN useradd bioshare -u 1234 -g 1234 -m -s /bin/bash
RUN mkdir /home/bioshare/.ssh
RUN touch /home/bioshare/.ssh/authorized_keys

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
