import os
import subprocess
import tempfile
import glob
import socket
from string import Formatter
from enum import Enum
from spark_connect_labextension.config import SPARK_HOME, SPARK_CONNECT_PORT, SPARK_CONNECT_PACKAGE


class ClusterStatus(Enum):
    STOPPED = "STOPPED"
    PROVISIONING = "PROVISIONING"
    READY = "READY"

class _SparkConnectCluster:
    def __init__(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.cluster_name = None
        self.config_bundles = []
        self.extra_config = {}
        self.options = {}
        self.started = False
        self.pre_script = None

    def start(self, cluster_name: str, options: dict = {}, envs: dict = None, config_bundles: dict = [], extra_config: dict = {}, pre_script: str = None):
        print("Starting Spark Connect server...")
        self.started = True
        self.cluster_name = cluster_name
        self.config_bundles = config_bundles
        self.extra_config = extra_config
        self.pre_script = pre_script

        self.tmpdir.cleanup()

        env_variables = self.get_envs(envs)
        if SPARK_HOME:
            env_variables['SPARK_HOME'] = SPARK_HOME
        env_variables['SPARK_LOG_DIR'] = self.tmpdir.name
        print("Spark log dir", self.tmpdir.name)

        self.options = options

        options['spark.connect.grpc.binding.port'] = str(self.get_port())
        # options['spark.ui.proxyRedirectUri'] = proxy_redirect_uri
        config_args = self.get_config_args(options)

        run_script = f"sh $SPARK_HOME/sbin/start-connect-server.sh --packages {SPARK_CONNECT_PACKAGE} {config_args}"
        if self.pre_script:
            run_script = self.pre_script + ' && ' + run_script
        
        retcode = subprocess.Popen(run_script, shell=True, env=env_variables).wait()
        if retcode != 0:
            raise Exception("Cannot start Spark Connect server")

    def stop(self):
        print("Stopping Spark Connect server...")
        env_variables = self.get_envs({})
        if SPARK_HOME:
            env_variables['SPARK_HOME'] = SPARK_HOME
        run_script = f"sh $SPARK_HOME/sbin/stop-connect-server.sh"
        if self.pre_script:
            run_script = self.pre_script + ' && ' + run_script

        retcode = subprocess.Popen(run_script, shell=True, env=env_variables).wait()
        if retcode != 0:
            raise Exception("Cannot stop Spark Connect server")
        self.started = False
            
    def get_log(self) -> str:
        logfile = self.get_logfile_path()
        if not logfile:
            return None

        with open(logfile, 'r') as f:
            return f.read()
    
    def get_logfile_path(self) -> str:
        files = glob.glob(self.tmpdir.name + '/*.out')
        if len(files) == 0:
            return None
        logfile = files[-1]
        return logfile

    def get_status(self) -> ClusterStatus:
        if not self.is_connect_server_running():
            return ClusterStatus.STOPPED
        if not self.is_server_ready():
            return ClusterStatus.PROVISIONING
        return ClusterStatus.READY
    
    def get_port(self) -> int:
        return SPARK_CONNECT_PORT
    
    def get_options(self) -> dict:
        return self.options
    
    def is_connect_server_running(self) -> bool:
        env_variables = self.get_envs({})
        if SPARK_HOME:
            env_variables['SPARK_HOME'] = SPARK_HOME

        run_script = f"sh $SPARK_HOME/sbin/spark-daemon.sh status org.apache.spark.sql.connect.service.SparkConnectServer 1"
        if self.pre_script:
            run_script = self.pre_script + ' && ' + run_script

        retcode = subprocess.Popen(run_script, shell=True, env=env_variables).wait()
        return retcode == 0

    def is_server_ready(self) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', self.get_port()))
        sock.close()
        return result == 0
 
    def get_envs(self, envs: dict) -> dict:
        my_env = os.environ.copy()
        if envs:
            for key in envs:
                my_env[key] = envs[key]
        return my_env

    def get_config_args(self, options: dict) -> str:
        if not options:
            return []
        
        args = []
        for key, val in options.items():
            args.append("--conf")
            val = self.replace_env_params(val)
            val = val.replace('"', '\\"')
            args.append(f'{key}="{val}"')
        return ' '.join(args)
    
    def replace_env_params(self, value):
        value = f"{value}"
        replacable_values = {}
        for _, variable, _, _ in Formatter().parse(value):
            if variable is  not None:
                replacable_values[variable] = os.getenv(variable, '')
            
        return value.format(**replacable_values)
    
    def __del__(self):
        if self.started:
            self.stop()


cluster = _SparkConnectCluster()
