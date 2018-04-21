#!/usr/bin/env python3

import argparse
import os
import shutil
import urllib.request
import zipfile
import json
import socket

import netaddr


arg_parser = argparse.ArgumentParser(description="Roskomnadzor ban registry checker")

arg_parser.add_argument("mode", type=str, choices=("fetch", "check"), help="run mode")
arg_parser.add_argument("host", type=str, nargs="*",
                        help="ip address, network or fqdn to check")
arg_parser.add_argument("--registry-url", type=str,
                        default="https://github.com/zapret-info/z-i/archive/master.zip",
                        help="Registry repository url")

script_args = arg_parser.parse_args()

if script_args.mode == "check" and not script_args.host:
    arg_parser.error("the host argument is required for check mode")


script_dir = os.path.dirname(__file__)
registry_dir = os.path.join(script_dir, "registry")
registry_archive = os.path.join(registry_dir, "registry.zip")
ips_data_file = os.path.join(registry_dir, "z-i-master/dump.csv")
fqdn_data_file = os.path.join(registry_dir, "z-i-master/nxdomain.txt")


def fetch():
    if not os.path.exists(registry_dir):
        os.mkdir(registry_dir)

    for file in os.listdir(registry_dir):
        file_path = os.path.join(registry_dir, file)

        if os.path.isfile(file_path):
            os.remove(file_path)
        else:
            shutil.rmtree(file_path)

    urllib.request.urlretrieve(script_args.registry_url, registry_archive)

    zip_f = zipfile.ZipFile(registry_archive, 'r')
    zip_f.extractall(registry_dir)
    zip_f.close()



def check(hosts):
    result = {}

    ips_data = open(ips_data_file, encoding="cp1251").readlines()[1:]
    fqdn_data = open(fqdn_data_file).readlines()

    for host in hosts:
        try:
            host_obj = netaddr.IPNetwork(host)
        except netaddr.core.AddrFormatError:
            host_obj = host

        ip_objs = []

        if type(host_obj) is str:
            try:
                host_ips = socket.gethostbyname_ex(host_obj)[2]

                for host_ip in host_ips:
                    ip_objs.append(netaddr.IPNetwork(host_ip))
            except (ValueError, socket.gaierror):
                host_ip = None

            for line in fqdn_data:
                fqdn_reg = line.strip()

                if fqdn_reg == host_obj:
                    result[host] = result.get(host, [])
                    result[host].append(fqdn_reg)
        else:
            ip_objs = [host_obj]

        for ip_obj in ip_objs:
            for line in ips_data:
                subnets = line.strip().split(";")[0].split("|")

                for subnet in subnets:
                    subnet_reg = subnet.strip()

                    try:
                        subnet_obj = netaddr.IPNetwork(subnet_reg)
                    except netaddr.core.AddrFormatError:
                        continue

                    if ip_obj in subnet_obj:
                        result[host] = result.get(host, [])
                        result[host].append(subnet_reg)

    if result:
        print(json.dumps(result))


if script_args.mode == "fetch":
    fetch()
elif script_args.mode == "check":
    check(script_args.host)
