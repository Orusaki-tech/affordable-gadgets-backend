#!/bin/bash
# Minimal bootstrap so Ansible can connect (install Python 3)
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get -qq update
apt-get -qq install -y python3 python3-pip
