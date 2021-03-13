# Gerapy Prometheus Exporter

This is a package for supporting Prometheus in Scrapy, also this
package is a module in [Gerapy](https://github.com/Gerapy/Gerapy).

And the source code is modified from [https://github.com/rangertaha/scrapy-prometheus-exporter](https://github.com/rangertaha/scrapy-prometheus-exporter).

## Installation

```shell script
pip3 install gerapy-prometheus-exporter
```

## Usage

Set it to settings.py:

```python
EXTENSIONS = {
    'gerapy_prometheus_exporter.extension.WebService': 500,
}
```

By default the extension is enabled. To disable the extension you need to set `PROMETHEUS_EXPORTER_ENABLED` to False.

The web server will listen on a port specified in `PROMETHEUS_EXPORTER_PORT` (by default, it will try to listen on port 9410)

The endpoint for accessing exported metrics is:

```
http://0.0.0.0:9410/metrics
```

## Settings

These are the settings that control the metrics exporter:

### PROMETHEUS_EXPORTER_ENABLED

Default: True

A boolean which specifies if the exporter will be enabled (provided its extension is also enabled).

### PROMETHEUS_EXPORTER_PORT

Default: [6080]

The port to use for the web service. If set to None or 0, a dynamically assigned port is used.

### PROMETHEUS_EXPORTER_HOST

Default: '0.0.0.0'

The interface the web service should listen on.

### PROMETHEUS_EXPORTER_PATH

Default: 'metrics'

The url path to access exported metrics Example:
```
http://0.0.0.0:9410/metrics
```

### PROMETHEUS_EXPORTER_UPDATE_INTERVAL

Default: 5

This extensions periodically collects stats for exporting. The interval in seconds between metrics updates can be controlled with this setting.