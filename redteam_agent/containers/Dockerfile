# Red Team Agent Sandbox Container
# Based on Kali Linux with pre-installed security tools

FROM kalilinux/kali-rolling:latest

LABEL maintainer="Red Team Agent"
LABEL version="2.0"
LABEL description="Autonomous penetration testing sandbox"

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Update and install essential tools
RUN apt-get update && apt-get install -y \
    # Network scanning
    nmap \
    netcat-traditional \
    tcpdump \
    wireshark-cli \
    \
    # Web scanning
    nikto \
    gobuster \
    dirb \
    \
    # Database tools
    sqlmap \
    \
    # Password cracking
    hydra \
    john \
    hashcat \
    \
    # Exploitation
    exploitdb \
    searchsploit \
    \
    # Post-exploitation
    mimikatz \
    powershell-empire \
    \
    # Utilities
    curl \
    wget \
    git \
    python3 \
    python3-pip \
    vim \
    tmux \
    htop \
    iputils-ping \
    dnsutils \
    whois \
    \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /workspace

# Create non-root user for safety (optional)
# RUN useradd -m redteam && chown -R redteam:redteam /workspace
# USER redteam

# Default command
CMD ["/bin/bash"]
