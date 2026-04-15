FROM kalilinux/kali-rolling:latest

RUN apt-get update && apt-get install -y \
    python3 python3-pip nmap nikto metasploit-framework net-tools iproute2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

COPY . /app
ENV PYTHONPATH=/app

ENTRYPOINT ["python3", "-m", "code.cli"]
