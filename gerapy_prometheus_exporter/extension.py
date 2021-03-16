import logging
from prometheus_client.twisted import MetricsResource
from prometheus_client import Counter, Summary, Gauge
from twisted.web.server import Site
from twisted.web import server, resource
from twisted.internet import task
from scrapy.exceptions import NotConfigured
from scrapy.utils.reactor import listen_tcp
from scrapy import signals
from gerapy_prometheus_exporter.settings import *

logger = logging.getLogger(__name__)


class WebService(Site):
    """
    Prometheus Metrics WebService
    """

    def __init__(self, crawler):
        if not crawler.settings.getbool('PROMETHEUS_EXPORTER_ENABLED', PROMETHEUS_EXPORTER_ENABLED):
            raise NotConfigured
        self.tasks = []
        self.stats = crawler.stats
        self.crawler = crawler
        self.name = crawler.settings.get('BOT_NAME')
        self.port = crawler.settings.get('PROMETHEUS_EXPORTER_PORT', [
                                         PROMETHEUS_EXPORTER_PORT])
        self.host = crawler.settings.get(
            'PROMETHEUS_EXPORTER_HOST', PROMETHEUS_EXPORTER_HOST)
        self.path = crawler.settings.get(
            'PROMETHEUS_EXPORTER_PATH', PROMETHEUS_EXPORTER_PATH)
        self.interval = crawler.settings.get(
            'PROMETHEUS_EXPORTER_UPDATE_INTERVAL', PROMETHEUS_EXPORTER_UPDATE_INTERVAL)

        self.scrapy_item_scraped = Gauge(
            'scrapy_items_scraped', 'Spider items scraped', ['spider'])
        self.scrapy_item_dropped = Gauge(
            'scrapy_items_dropped', 'Spider items dropped', ['spider'])
        self.scrapy_response_received = Gauge(
            'scrapy_response_received', 'Spider responses received', ['spider'])
        self.scrapy_opened = Gauge('scrapy_opened', 'Spider opened', ['spider'])
        self.scrapy_closed = Gauge(
            'scrapy_closed', 'Spider closed', ['spider', 'reason'])

        self.scrapy_downloader_request_bytes = Gauge(
            'scrapy_downloader_request_bytes', '...', ['spider'])
        self.scrapy_downloader_request_total = Gauge(
            'scrapy_downloader_request_total', '...', ['spider'])
        self.scrapy_downloader_request_count = Gauge(
            'scrapy_downloader_request', '...', ['spider', 'method'])
        self.scrapy_downloader_response_count = Gauge(
            'scrapy_downloader_response', '...', ['spider'])
        self.scrapy_downloader_response_bytes = Gauge(
            'scrapy_downloader_response_bytes', '...', ['spider'])
        self.scrapy_downloader_response_status_count = Gauge(
            'scrapy_downloader_response_status', '...', ['spider', 'code'])

        self.scrapy_log_count = Gauge('scrapy_log', '...', ['spider', 'level'])

        self.scrapy_duplicate_filtered = Gauge(
            'scrapy_duplicate_filtered', '...', ['spider'])

        self.scrapy_memdebug_gc_garbage_count = Gauge(
            'scrapy_memdebug_gc_garbage', '...', ['spider'])
        self.scrapy_memdebug_live_refs = Gauge(
            'scrapy_memdebug_live_refs', '...', ['spider'])
        self.scrapy_memusage_max = Gauge(
            'scrapy_memusage_max', '...', ['spider'])
        self.scrapy_memusage_startup = Gauge(
            'scrapy_memusage_startup', '...', ['spider'])

        self.scrapy_scheduler_dequeued = Gauge(
            'scrapy_scheduler_dequeued', '...', ['spider'])
        self.scrapy_scheduler_enqueued = Gauge(
            'scrapy_scheduler_enqueued', '...', ['spider'])
        self.scrapy_scheduler_enqueued_memory = Gauge(
            'scrapy_scheduler_enqueued_memory', '...', ['spider'])

        self.scrapy_offsite_domains_count = Gauge(
            'scrapy_offsite_domains', '...', ['spider'])
        self.scrapy_offsite_filtered_count = Gauge(
            'scrapy_offsite_filtered', '...', ['spider'])

        self.scrapy_request_depth = Gauge(
            'scrapy_request_depth', '...', ['spider'])
        self.scrapy_request_depth_max = Gauge(
            'scrapy_request_depth_max', '...', ['spider'])

        root = resource.Resource()
        self.promtheus = None
        root.putChild(self.path.encode('utf-8'), MetricsResource())
        server.Site.__init__(self, root)

        crawler.signals.connect(self.engine_started, signals.engine_started)
        crawler.signals.connect(self.engine_stopped, signals.engine_stopped)

        crawler.signals.connect(self.spider_opened, signals.spider_opened)
        crawler.signals.connect(self.spider_closed, signals.spider_closed)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def engine_started(self):
        # Start server endpoint for exporting metrics
        self.promtheus = listen_tcp(self.port, self.host, self)

        # Periodically update the metrics
        tsk = task.LoopingCall(self.update)
        self.tasks.append(tsk)
        tsk.start(self.interval, now=True)

    def engine_stopped(self):
        # Stop all periodic tasks
        for tsk in self.tasks:
            if tsk.running:
                tsk.stop()

        # Stop metrics exporting
        self.promtheus.stopListening()

    def spider_opened(self, spider):
        self.scrapy_opened.labels(spider=self.name).inc()

    def spider_closed(self, spider, reason):
        self.scrapy_closed.labels(spider=self.name, reason=reason).inc()

    def update(self):
        logging.debug(self.stats.get_stats())

        # Downloader Request Stats
        self.request_stats()

        # Downloader Request Stats
        self.response_stats()

        # Logging Stats
        self.logging_stats()

        # Items Stats
        self.item_stats()

        # Memory Debug Stats
        self.memory_debug_stats()

        # Memory Usage Stats
        self.memory_usage_stats()

        # Scheduler Stats
        self.scheduler_stats()

        # Off-Site Filtering Stats
        self.offsite_stats()

        # Duplicate Stats
        self.duplicate_filter_stats()

        # Request Depth
        self.request_depth()

    def item_stats(self):
        scraped_count = self.stats.get_value('item_scraped_count', 0)
        self.scrapy_item_scraped.labels(spider=self.name).set(scraped_count)
        dropped_count = self.stats.get_value('item_dropped_count', 0)
        self.scrapy_item_dropped.labels(spider=self.name).set(dropped_count)

    def request_depth(self):
        depth = self.stats.get_value('request_depth_max', 0)
        self.scrapy_request_depth_max.labels(spider=self.name).set(depth)
        for i in range(depth):
            stat = 'request_depth_count/{}'.format(i)
            depthv = self.stats.get_value(stat, 0)
            self.scrapy_request_depth.labels(spider=self.name).set(depthv)

    def duplicate_filter_stats(self):
        dup = self.stats.get_value('dupefilter/filtered', 0)
        self.scrapy_duplicate_filtered.labels(spider=self.name).set(dup)

    def memory_debug_stats(self):
        mdgc_count = self.stats.get_value('memdebug/gc_garbage_count', 0)
        self.scrapy_memdebug_gc_garbage_count.labels(
            spider=self.name).set(mdgc_count)

        mdlr_count = self.stats.get_value('memdebug/live_refs/MySpider', 0)
        self.scrapy_memdebug_live_refs.labels(
            spider=self.name).set(mdlr_count)

    def memory_usage_stats(self):
        mum_count = self.stats.get_value('memusage/max', 0)
        self.scrapy_memusage_max.labels(spider=self.name).set(mum_count)

        mus_count = self.stats.get_value('memusage/startup', 0)
        self.scrapy_memusage_startup.labels(spider=self.name).set(mus_count)

    def scheduler_stats(self):
        dequeued = self.stats.get_value('scheduler/dequeued', 0)
        self.scrapy_scheduler_dequeued.labels(spider=self.name).set(dequeued)

        enqueued = self.stats.get_value('scheduler/enqueued', 0)
        self.scrapy_scheduler_enqueued.labels(spider=self.name).set(enqueued)

        enqueued_mem = self.stats.get_value('scheduler/enqueued/memory', 0)
        self.scrapy_scheduler_enqueued_memory.labels(
            spider=self.name).set(enqueued_mem)

        dequeued_mem = self.stats.get_value('scheduler/dequeued/memory', 0)
        self.scrapy_scheduler_enqueued_memory.labels(
            spider=self.name).set(dequeued_mem)

    def offsite_stats(self):
        od_count = self.stats.get_value('offsite/domains', 0)
        self.scrapy_offsite_domains_count.labels(
            spider=self.name).set(od_count)

        of_count = self.stats.get_value('offsite/filtered', 0)
        self.scrapy_offsite_filtered_count.labels(
            spider=self.name).set(of_count)

    def request_stats(self):
        for i in ['GET', 'PUT', 'DELETE', 'POST']:
            stat = 'downloader/request_method_count/{}'.format(i)
            count = self.stats.get_value(stat, 0)
            if count > 0:
                self.scrapy_downloader_request_count.labels(
                    spider=self.name, method=i).set(count)

        total_count = self.stats.get_value('downloader/request_count', 0)
        self.scrapy_downloader_request_total.labels(
            spider=self.name).set(total_count)

        request_bytes = self.stats.get_value('downloader/request_bytes', 0)
        self.scrapy_downloader_request_bytes.labels(
            spider=self.name).set(request_bytes)

    def response_stats(self):
        response_count = self.stats.get_value('downloader/response_count', 0)
        self.scrapy_downloader_response_count.labels(
            spider=self.name).set(response_count)

        for i in ['200', '404', '500']:
            stat = 'downloader/response_status_count/{}'.format(i)
            status = self.stats.get_value(stat, 0)
            self.scrapy_downloader_response_status_count.labels(
                spider=self.name, code=i).set(status)

        response_bytes = self.stats.get_value('downloader/response_bytes', 0)
        self.scrapy_downloader_response_bytes.labels(
            spider=self.name).set(response_bytes)

    def logging_stats(self):
        for i in ['DEBUG', 'ERROR', 'INFO', 'CRITICAL', 'WARNING']:
            level = self.stats.get_value('log_count/{}'.format(i), 0)
            self.scrapy_log_count.labels(
                spider=self.name, level=i).set(level)
