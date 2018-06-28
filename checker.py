#!/usr/bin/env python3

import argparse
import os
import shutil
import urllib.request
import zipfile
import json
import socket
import glob
import sqlite3
import math

import netaddr


class RknChecker(object):
    def __init__(self, cache_dir=None):
        app_dir = os.path.dirname(__file__)

        self.cache_dir = cache_dir or os.path.join(app_dir, "cache")
        self.registry_db_file = os.path.join(self.cache_dir, "registry.db")

    def fetch(self, registry_url):
        registry_dir = os.path.join(self.cache_dir, "registry")
        registry_db_file_temp = "{}.tmp".format(self.registry_db_file)

        self._mkdir_if_not_exists(self.cache_dir)

        self._fetch_registry(registry_url, registry_dir)
        self._fill_database(registry_dir, registry_db_file_temp)

        self._commit_fetch(registry_db_file_temp)

    @staticmethod
    def _mkdir_if_not_exists(dir_path):
        if not os.path.exists(dir_path):
            os.mkdir(dir_path)

    @staticmethod
    def _rm_file_if_exists(file_path):
        if os.path.exists(file_path):
            os.remove(file_path)

    def _fetch_registry(self, registry_url, registry_dir):
        registry_arch_file = os.path.join(self.cache_dir, "registry.zip")

        urllib.request.urlretrieve(registry_url, registry_arch_file)

        self._mkdir_if_not_exists(registry_dir)
        self._unzip_file(registry_arch_file, registry_dir)

    @staticmethod
    def _unzip_file(file_path, dir_path):
        zip_f = zipfile.ZipFile(file_path, "r")
        zip_f.extractall(dir_path)
        zip_f.close()

    def _fill_database(self, registry_dir, db_file_path):
        self._rm_file_if_exists(db_file_path)
        db_conn = sqlite3.connect(db_file_path)

        self._prepare_database(db_conn)

        self._fill_db_ips_data(db_conn, registry_dir)
        self._fill_db_fqdn_data(db_conn, registry_dir)

        db_conn.close()

    @staticmethod
    def _prepare_database(db_conn):
        db_cursor = db_conn.cursor()

        db_cursor.execute("CREATE TABLE ip_networks (start_addr INTEGER, end_addr INTEGER)")
        db_cursor.execute("CREATE INDEX ip_netw_start_addr ON ip_networks (start_addr)")
        db_cursor.execute("CREATE INDEX ip_netw_end_addr ON ip_networks (end_addr)")

        db_cursor.execute("CREATE TABLE fqdns (fqdn TEXT)")
        db_cursor.execute("CREATE INDEX fqdns_fqdn ON fqdns (fqdn)")

    def _fill_db_ips_data(self, db_conn, registry_dir):
        registry_ips_file = glob.glob(os.path.join(registry_dir, "**", "dump.csv"), recursive=True)[0]

        ips_data = self._load_ips_data(registry_ips_file)
        self._save_db_data(ips_data, db_conn, "INSERT INTO ip_networks (start_addr, end_addr) VALUES (?, ?)",
                           lambda r: (r["start_addr"], r["end_addr"]))

    @staticmethod
    def _load_ips_data(file_path):
        data = []

        file_lines = open(file_path, encoding="cp1251").readlines()[1:]

        for line in file_lines:
            networks = line.strip().split(";")[0].split("|")

            for network in networks:
                network_reg = network.strip()

                try:
                    network_obj = netaddr.IPNetwork(network_reg)
                except netaddr.core.AddrFormatError:
                    continue

                data_rec = {
                    "start_addr": network_obj.first,
                    "end_addr":   network_obj.last,
                }

                data.append(data_rec)

        return data

    def _fill_db_fqdn_data(self, db_conn, registry_dir):
        registry_fqdn_file = glob.glob(os.path.join(registry_dir, "**", "nxdomain.txt"), recursive=True)[0]

        fqdn_data = self._load_fqdn_data(registry_fqdn_file)
        self._save_db_data(fqdn_data, db_conn, "INSERT INTO fqdns (fqdn) VALUES (?)", lambda r: (r,))

    @staticmethod
    def _save_db_data(data, db_conn, sql, parameters_fn=None):
        db_cursor = db_conn.cursor()

        for data_rec in data:
            if parameters_fn:
                parameters = parameters_fn(data_rec)
            else:
                parameters = data_rec

            db_cursor.execute(sql, parameters)

        db_conn.commit()

    @staticmethod
    def _load_fqdn_data(file_path):
        data = []

        file_lines = open(file_path).readlines()

        for line in file_lines:
            fqdn_reg = line.strip().lower()
            data.append(fqdn_reg)

        return data

    def _commit_fetch(self, registry_db_file_temp):
        os.rename(registry_db_file_temp, self.registry_db_file)

        self._cleanup_cache_dir()

    def _cleanup_cache_dir(self):
        for node in os.listdir(self.cache_dir):
            node_path = os.path.join(self.cache_dir, node)

            if os.path.isfile(node_path):
                if node_path == self.registry_db_file:
                    continue

                os.remove(node_path)
            else:
                shutil.rmtree(node_path)

    def check(self, host):
        hosts = host if isinstance(host, list) else [host]
        db_conn = sqlite3.connect(self.registry_db_file)

        result = self._check_hosts(hosts, db_conn)
        db_conn.close()

        return result

    def _check_hosts(self, hosts, db_conn):
        result = {}

        for host in hosts:
            host_results = self._check_host(host, db_conn)

            if host_results:
                result[host] = host_results

        return result

    def _check_host(self, host, db_conn):
        results = []

        host_objs = self._get_host_objs(host)

        for host_obj in host_objs:
            host_obj_results = self._check_host_obj(host_obj, db_conn)

            if host_obj_results:
                results += host_obj_results

        return results

    def _get_host_objs(self, host):
        host_objs = []

        host_obj = self._get_host_obj(host)
        host_objs.append(host_obj)

        if isinstance(host_obj, str):
            ip_objs = self._get_fqdn_ip_objs(host_obj)
            host_objs += ip_objs

        return host_objs

    @staticmethod
    def _get_host_obj(host):
        try:
            host_obj = netaddr.IPAddress(host)
        except ValueError:
            host_obj = netaddr.IPNetwork(host)
        except netaddr.core.AddrFormatError:
            host_obj = host

        return host_obj

    @staticmethod
    def _get_fqdn_ip_objs(fqdn):
        ip_objs = []

        try:
            fqdn_ips = socket.gethostbyname_ex(fqdn)[2]

            for fqdn_ip in fqdn_ips:
                ip_obj = netaddr.IPAddress(fqdn_ip)
                ip_objs.append(ip_obj)
        except (ValueError, socket.gaierror):
            pass

        return ip_objs

    def _check_host_obj(self, host_obj, db_conn):
        results = []

        if isinstance(host_obj, str):
            result = self._check_fqdn(host_obj, db_conn)

            if result:
                results = [result]
        else:
            results = self._check_ipnet_obj(host_obj, db_conn)

        return results

    @staticmethod
    def _check_fqdn(fqdn, db_conn):
        result = None
        db_cursor = db_conn.cursor()

        db_cursor.execute("SELECT fqdn FROM fqdns WHERE fqdn = ?", (fqdn.lower(),))
        select_result = db_cursor.fetchone()

        if select_result:
            result = select_result[0]

        return result

    def _check_ipnet_obj(self, ipnet_obj, db_conn):
        results = []
        db_cursor = db_conn.cursor()

        if isinstance(ipnet_obj, netaddr.IPAddress):
            db_cursor.execute("""SELECT start_addr, end_addr FROM ip_networks WHERE ? BETWEEN start_addr AND end_addr""",
                            (int(ipnet_obj),))
        else:
            db_cursor.execute("""SELECT start_addr, end_addr FROM ip_networks WHERE ? BETWEEN start_addr AND end_addr
                                                                              AND ? BETWEEN start_addr AND end_addr""",
                            (ipnet_obj.first, ipnet_obj.last))

        select_results = db_cursor.fetchall()

        for select_result in select_results:
            start_addr = select_result[0]
            end_addr = select_result[1]

            network_obj = self._get_network_obj(start_addr, end_addr)

            results.append(str(network_obj))

        return results

    @staticmethod
    def _get_network_obj(start_addr, end_addr):
        network_addr = start_addr
        network_mask = 32 - round(math.log2(end_addr - start_addr + 1))

        network_obj = netaddr.IPNetwork((network_addr, network_mask))

        return network_obj


def parse_args():
    arg_parser = argparse.ArgumentParser(description="Roskomnadzor prohibited resources registry checker")

    arg_parser.add_argument("mode", type=str, choices=("fetch", "check"), help="run mode")
    arg_parser.add_argument("host", type=str, nargs="*",
                            help="ip address, network or fqdn to check")
    arg_parser.add_argument("--registry-url", type=str,
                            default="https://github.com/zapret-info/z-i/archive/master.zip",
                            help="registry url")

    args = arg_parser.parse_args()

    if args.mode == "check" and not args.host:
        arg_parser.error("at least one host argument is required in check mode")

    return args


if __name__ == "__main__":
    args = parse_args()
    result = None

    rkn_checker = RknChecker()

    if args.mode == "fetch":
        rkn_checker.fetch(args.registry_url)
    elif args.mode == "check":
        result = rkn_checker.check(args.host)

    if result:
        json_data = json.dumps(result)
        print(json_data)