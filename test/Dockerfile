FROM debian:trixie-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends firefox-esr python3 python3-selenium curl ca-certificates fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*
ARG GECKODRIVER=0.36.0
RUN curl -fsSL "https://github.com/mozilla/geckodriver/releases/download/v${GECKODRIVER}/geckodriver-v${GECKODRIVER}-linux64.tar.gz" \
  | tar -xz -C /usr/local/bin geckodriver
