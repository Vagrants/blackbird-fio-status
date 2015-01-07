"""
blackbird fio-status module

'/usr/bin/fio-status' needs root privilege,
so blackbird user (default bbd) must be able to sudo with NOPASSWD.

# cat /etc/sudoers.d/bbd
Defaults:bbd !requiretty
bbd ALL=(ALL) NOPASSWD: /usr/bin/fio-status

Or you must run blackbird in root user.

# cat /etc/blackbird/defaults.cfg
[global]
user = root
group = root

"""

__VERSION__ = '0.1.0'

from blackbird.plugins import base
import subprocess

try:
    # pylint: disable=import-error
    import simplejson as json
except ImportError:
    import json


class ConcreteJob(base.JobBase):
    """
    This class is Called by "Executor".
    Get aeropike information and send to backend server.
    """

    def __init__(self, options, queue=None, logger=None):
        super(ConcreteJob, self).__init__(options, queue, logger)

    def build_items(self):
        """
        main loop
        """

        # ping item
        self.ping()

        # get fio-status
        self.fio_status()

    def build_discovery_items(self):
        """
        main loop for lld
        """

        # discovery adapter,device,vsu
        self.fio_lld()

    def ping(self):
        """
        send ping item
        """

        self._enqueue('blackbird.fio-status.ping', 1)
        self._enqueue('blackbird.fio-status.version', __VERSION__)

    def fio_status(self):
        """
        get fio-status
        """

        fio = self._fio_exec()

        # adapter
        if 'adapter' in fio:
            self._fio_adapter(fio['adapter'])

        # host
        if 'host' in fio:
            self._fio_host(fio['host'])

        # version
        if 'version' in fio:
            self._fio_version(fio['version'])

    # pylint: disable=too-many-locals
    def fio_lld(self):
        """
        discover adapter number, device name, and vsu name
        """

        _adapter_list = []
        _device_list = []
        _vsu_list = []
        _host_list = []

        fio = self._fio_exec()

        # discover adapter
        if 'adapter' in fio:

            adapter_index = 0
            for adapter in fio['adapter']:
                adapter_index += 1
                adapter_name = 'Adapter{index}'.format(index=adapter_index)
                _adapter_list.append({'{#ADAPTER}': adapter_name})

                if 'iomemory' in adapter:
                    for iomemory in adapter['iomemory']:
                        device_name = iomemory['device_path']
                        _device_list.append({
                            '{#ADAPTER}': adapter_name,
                            '{#DEVICE}': device_name,
                        })

                        for vsu in iomemory['vsu']:
                            vsu_name = vsu['device_path']
                            _vsu_list.append({
                                '{#ADAPTER}': adapter_name,
                                '{#DEVICE}': device_name,
                                '{#VSU}': vsu_name,
                            })

        # dicover host
        if 'host' in fio:

            host_index = 0
            for _ in fio['host']:
                host_index += 1
                host_name = 'host{hindex}'.format(hindex=host_index)
                _host_list.append({'{#HOST}': host_name})

        self._enqueue_lld('fio.adapter.LLD', _adapter_list)
        self._enqueue_lld('fio.device.LLD', _device_list)
        self._enqueue_lld('fio.vsu.LLD', _vsu_list)
        self._enqueue_lld('fio.host.LLD', _host_list)

    def _fio_exec(self):
        """
        execute fio-status
        """

        try:
            fio_process = subprocess.Popen(
                ['sudo', self.options['path'], '-aU', '-fj'],
                stdout=subprocess.PIPE,
            )
            output = fio_process.communicate()[0]
        except OSError as err:
            raise base.BlackbirdPluginError(
                'can not exec {path} [{err}]'
                ''.format(path=self.options['path'], err=err)
            )

        try:
            fio = json.loads(output)
        except (ValueError, TypeError):
            raise base.BlackbirdPluginError(
                'can not load fio-status output'
            )

        return fio

    def _fio_adapter(self, adapters):
        """
        enqueue adapter section
        """

        adapter_index = 0
        for adapter in adapters:

            # incr adapter index
            adapter_index += 1
            adapter_name = 'Adapter{index}'.format(index=adapter_index)

            for adapter_key in adapter.keys():

                # skip iomemory
                if isinstance(adapter[adapter_key], list):
                    continue

                item_key = (
                    'fio.status.adapter[{adapter},{adapter_key}]'
                    ''.format(adapter=adapter_name, adapter_key=adapter_key)
                )
                self._enqueue(item_key, adapter[adapter_key])

            # iomemory
            for iomemory in adapter['iomemory']:

                # detect device name
                iomemory_device = iomemory['device_path']

                for iomemory_key in iomemory.keys():

                    # skip vsu
                    if isinstance(iomemory[iomemory_key], list):
                        continue

                    item_key = (
                        'fio.status.adapter.iomemory[{adapter},{dev},{ikey}]'
                        ''.format(
                            adapter=adapter_name,
                            dev=iomemory_device,
                            ikey=iomemory_key
                        )
                    )
                    self._enqueue(item_key, iomemory[iomemory_key])

                # vsu
                for vsu in iomemory['vsu']:

                    # detect device name
                    vsu_device = vsu['device_path']

                    for vsu_key in vsu.keys():
                        item_key = (
                            'fio.status.adapter.iomemory.vsu'
                            '[{adapter},{dev},{vsu},{vkey}]'
                            ''.format(
                                adapter=adapter_name,
                                dev=iomemory_device,
                                vsu=vsu_device,
                                vkey=vsu_key
                            )
                        )
                        self._enqueue(item_key, vsu[vsu_key])

    def _fio_host(self, hosts):
        """
        enqueue host section
        """

        host_index = 0
        for host in hosts:

            # incr host index
            host_index += 1

            for _key, _val in host.items():
                item_key = (
                    'fio.status.host[host{hindex},{key}]'
                    ''.format(hindex=host_index, key=_key)
                )
                self._enqueue(item_key, _val)

    def _fio_version(self, version):
        """
        enqueue version section
        """

        self._enqueue('fio.status.version', version)

    def _enqueue(self, key, value):
        """
        wrap queue method
        """

        item = FioItem(
            key=key,
            value=value,
            host=self.options['hostname']
        )
        self.queue.put(item, block=False)
        self.logger.debug(
            'Inserted to queue {key}:{value}'
            ''.format(key=key, value=value)
        )

    def _enqueue_lld(self, key, value):
        """
        wrap queue method for low level discovery
        """

        item = base.DiscoveryItem(
            key=key,
            value=value,
            host=self.options['hostname']
        )
        self.queue.put(item, block=False)
        self.logger.debug(
            'Inserted to queue {key}:{value}'
            ''.format(key=key, value=str(value))
        )


# pylint: disable=too-few-public-methods
class FioItem(base.ItemBase):
    """
    fio-status Item Class
    """

    def __init__(self, key, value, host):
        super(FioItem, self).__init__(key, value, host)

        self._data = {}
        self._generate()

    @property
    def data(self):
        return self._data

    def _generate(self):
        self._data['key'] = self.key
        self._data['value'] = self.value
        self._data['host'] = self.host
        self._data['clock'] = self.clock


class Validator(base.ValidatorBase):
    """
    Validate configuration.
    """

    def __init__(self):
        self.__spec = None

    @property
    def spec(self):
        self.__spec = (
            "[{0}]".format(__name__),
            "path=string(default='/usr/bin/fio-status')",
            "hostname=string(default={0})".format(self.detect_hostname()),
        )
        return self.__spec
