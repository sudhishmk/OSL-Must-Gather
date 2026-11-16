ARG OPENSHIFT_VERSION=4.19
FROM quay.io/openshift/origin-must-gather:${OPENSHIFT_VERSION}

USER 0
RUN dnf install -y --setopt=install_weak_deps=False python3 python3-pyyaml \
    && dnf clean all
COPY collection-scripts/gather /usr/bin/gather
COPY collection-scripts/osl-sanitize.py /usr/bin/osl-sanitize.py
RUN chmod 0755 /usr/bin/gather /usr/bin/osl-sanitize.py \
    && command -v oc && command -v timeout \
    && python3 -c 'import yaml'
ENV OSL_SANITIZER=/usr/bin/osl-sanitize.py
WORKDIR /must-gather
CMD ["/usr/bin/gather"]
