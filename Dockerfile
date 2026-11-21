FROM docker.io/matrixdotorg/synapse:v1.165.0@sha256:673b4223c81a7634fd07d832b939a58f97081cfdaae7cdd2d1664cdcf7611b62
ENV PYTHONPATH=/opt/relay
COPY relay_policy.py patch_device.py /opt/relay/
RUN python /opt/relay/patch_device.py
