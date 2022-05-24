#!/bin/bash
podman stop -a 
podman rm -a
#podman build --rm -t newtvshows_ng:latest "."
podman-compose -f docker-compose-production.yml up -d
