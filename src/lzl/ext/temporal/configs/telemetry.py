from __future__ import annotations

"""
TemporalIO Telemetry Config
"""

import os
import json
import typing as t
from lzl import load
from datetime import timedelta
from pydantic.types import Json
from lzo.types import BaseSettings, model_validator, Field
from lzl.types import eproperty, create_alias_choices

if t.TYPE_CHECKING:
    from temporalio.worker import Interceptor
    from temporalio.runtime import PrometheusConfig, TelemetryConfig
    from temporalio.runtime import OpenTelemetryMetricTemporality, OpenTelemetryConfig
    from temporalio.contrib.opentelemetry import TracingInterceptor

if load.TYPE_CHECKING:
    import opentelemetry
    from opentelemetry.exporter.otlp.proto.grpc import trace_exporter as otlp_trace_exporter
    import temporalio.runtime as temporal_runtime

else:
    
    opentelemetry = load.LazyLoad("opentelemetry", "opentelemetry-sdk", install_missing=True)
    otlp_trace_exporter = load.LazyLoad("opentelemetry.exporter.otlp.proto.grpc.trace_exporter", "opentelemetry-exporter-otlp", install_missing=True)
    temporal_runtime = load.LazyLoad("temporalio.runtime", "temporalio", install_missing=True)


prom_alias_prefixes = [
    'prometheus', 'telemetry', 'monitoring',
]
otel_alias_prefixes = [
    'otel', 'opentelemetry', 'tracing',
]

class TemporalPrometheusSettings(BaseSettings):
    """
    Temporal Settings for Prometheus
    """
    disabled: t.Optional[bool] = Field(
        None, 
        description = "If true, the Prometheus endpoint will not be exposed",
        validation_alias = create_alias_choices('disabled', *prom_alias_prefixes, key_pos = 'suffix')
    )
    # Allow for explicitly enabling Prometheus
    enabled: t.Optional[bool] = Field(
        None, 
        description = "If true, the Prometheus port will be exposed",
        validation_alias = create_alias_choices('enabled', *prom_alias_prefixes, key_pos = 'suffix')
    )

    address: t.Optional[str] = Field(
        None, 
        description = "The address to bind the Prometheus server to",
        validation_alias = create_alias_choices('address', 'prometheus', key_pos = 'suffix')
    )

    counters_total_suffix: t.Optional[bool] = Field(
        None, 
        description = "If true, the total counters will be exposed",
        validation_alias = create_alias_choices('counters_total_suffix', 'prometheus', key_pos = 'suffix')
    )

    unit_suffix: t.Optional[bool] = Field(
        None, 
        description = "If true, the unit suffix will be appended to the metrics",
        validation_alias = create_alias_choices('unit_suffix', 'prometheus', key_pos = 'suffix')
    )

    durations_as_seconds: t.Optional[bool] = Field(
        None, 
        description = "If true, durations will be exposed as seconds",
        validation_alias = create_alias_choices('durations_as_seconds', 'prometheus', key_pos = 'suffix')
    )

    class Config(BaseSettings.Config):
        env_prefix = "TEMPORAL_PROMETHEUS_"
    
    @model_validator(mode = 'after')
    def validate_prometheus(self):
        """
        Validates the Prometheus
        """
        if self.enabled:
            if not self.address: self.address = '0.0.0.0:9000'
        return self

    @eproperty
    def is_enabled(self) -> bool:
        """
        Returns whether the Prometheus is enabled
        """
        if self.enabled is not None: return self.enabled
        return self.address is not None if self.disabled is None else not self.disabled


    def update(self, data: t.Dict[str, t.Any]):
        """
        Updates the data
        """
        for key, value in data.items():

            if key in {'address', 'disabled'} and value is not None:
                _ = self._extra.pop('is_enabled', None)

            if hasattr(self, key): setattr(self, key, value)

    def get_config(self, **kwargs) -> 'PrometheusConfig':
        """
        Returns the Prometheus Config
        """
        kws = {
            'bind_address': self.address,
            'counters_total_suffix': self.counters_total_suffix,
            'unit_suffix': self.unit_suffix,
            'durations_as_seconds': self.durations_as_seconds,
        }
        if kwargs: kws.update(kwargs)
        kws = {k:v for k,v in kws.items() if v is not None}
        from temporalio.runtime import PrometheusConfig
        return PrometheusConfig(**kws)
    
    def get_interceptor(self, **kwargs) -> None:
        """
        Returns the Interceptors
        """
        return None

    def init_runtime(
        self, 
        **kwargs,
    ):
        """
        Initializes the Runtime for Prometheus
        """
        pass

class TemporalOTELSettings(BaseSettings):
    """
    Temporal Settings for OTEL
    """
    disabled: t.Optional[bool] = Field(
        None, 
        description = "If true, OpenTelemetry will not be enabled",
        validation_alias = create_alias_choices('disabled', *otel_alias_prefixes, key_pos = 'suffix')
    )

    url: t.Optional[str] = Field(
        None, 
        description = "The URL to use for the OTEL exporter",
        validation_alias = create_alias_choices('url', *otel_alias_prefixes, key_pos = 'suffix')
    )

    headers: t.Optional[Json] = Field(
        None, 
        description = "The headers to use for the OTEL exporter",
        validation_alias = create_alias_choices('headers', *otel_alias_prefixes, key_pos = 'suffix')
    )

    periodicity: t.Optional[str] = Field(
        'minutes=1', 
        description = "The metric periodicity to use for the OTEL exporter. Format should be comma-seperated <period>=<value>",
        validation_alias = create_alias_choices('periodicity', *otel_alias_prefixes, key_pos = 'suffix'),
        examples = [
            'minutes=1,seconds=30',
            'seconds=30',
        ]
    )

    temporality: t.Optional[str] = Field(
        None, 
        description = "The metric temporality to use for the OTEL exporter. Options are: CUMULATIVE, DELTA",
        validation_alias = create_alias_choices('temporality', *otel_alias_prefixes, key_pos = 'suffix'),
    )

    durations_as_seconds: t.Optional[bool] = Field(
        None, 
        description = "If true, durations will be exposed as seconds",
        validation_alias = create_alias_choices('durations_as_seconds',  *otel_alias_prefixes, key_pos = 'suffix')
    )

    service_name: t.Optional[str] = Field(
        None, 
        description = "The service name to use for the OTEL exporter",
        validation_alias = create_alias_choices('service_name', *otel_alias_prefixes, key_pos = 'suffix')
    )

    class Config(BaseSettings.Config):
        env_prefix = "TEMPORAL_OTEL_"
    
    @model_validator(mode = 'after')
    def validate_otel(self):
        """
        Validates the OTEL
        """
        if self.url:
            if not self.url.startswith('http'):
                if 'cluster.local' in self.url or 'localhost' in self.url:
                    self.url = f'http://{self.url}'
                else:
                    self.url = f'https://{self.url}'
        
        return self
    

    @eproperty
    def enabled(self) -> bool:
        """
        Returns whether the OTEL is enabled
        """
        return self.url is not None if self.disabled is None else not self.disabled
    
    @eproperty
    def insecure(self) -> bool:
        """
        Returns whether the OTEL is insecure
        """
        return self.url.startswith('http://') if self.url else False

    @eproperty
    def metric_periodicity(self) -> timedelta:
        """
        Returns the metric periodicity
        """
        kws = {period: int(value) for period, value in self.periodicity.split(',')}
        return timedelta(**kws)

    @eproperty
    def metric_temporality(self) -> t.Optional['OpenTelemetryMetricTemporality']:
        """
        Returns the metric temporality
        """
        if self.temporality is None: return None
        from temporalio.runtime import OpenTelemetryMetricTemporality
        return OpenTelemetryMetricTemporality[self.temporality.upper()]
    
    def update(self, data: t.Dict[str, t.Any]):
        """
        Updates the data
        """
        for key, value in data.items():
            if key == 'periodicity':
                if isinstance(value, timedelta):
                    self._extra['metric_periodicity'] = value
                    continue
                _ = self._extra.pop('metric_periodicity', None)
            
            if key == 'temporality':
                if hasattr(value, 'value'):
                    self._extra['metric_temporality'] = value.value
                    continue
                _ = self._extra.pop('metric_temporality', None)
            
            if key == 'headers':
                if isinstance(value, str): value = json.loads(value)
            
            if key in {'url', 'disabled'} and value is not None:
                _ = self._extra.pop('enabled', None)

            if hasattr(self, key): setattr(self, key, value)

    def get_config(self, **kwargs) -> 'OpenTelemetryConfig':
        """
        Returns the OTEL Config
        """
        kws = {
            'url': self.url,
            'headers': self.headers,
            'metric_periodicity': self.metric_periodicity,
            'metric_temporality': self.metric_temporality,
            'durations_as_seconds': self.durations_as_seconds,
        }
        if kwargs: kws.update(kwargs)
        kws = {k:v for k,v in kws.items() if v is not None}
        from temporalio.runtime import OpenTelemetryConfig
        return OpenTelemetryConfig(**kws)
    
    def get_interceptor(self, init: t.Optional[bool] = None, **kwargs) -> 'TracingInterceptor' | t.Type['TracingInterceptor']:
        """
        Returns the Interceptors
        """
        from temporalio.contrib.opentelemetry import TracingInterceptor
        return TracingInterceptor() if init else TracingInterceptor
    
    @eproperty
    def _has_init_runtime(self) -> bool:
        """
        Returns whether the Runtime has been initialized
        """
        return False

    def init_runtime(
        self, 
        service_name: t.Optional[str] = None,
        **kwargs,
    ):
        """
        Initializes the Runtime for OTEL
        """
        if not self.enabled: return
        service_name = service_name or self.service_name
        if not service_name: raise ValueError('Service Name must be provided')
        if self._has_init_runtime: return

        opentelemetry.__reload__()
        otlp_trace_exporter.__reload__()
        from opentelemetry import trace
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # Setup global tracer for workflow traces
        provider = TracerProvider(resource = Resource.create({SERVICE_NAME: service_name}))
        exporter = otlp_trace_exporter.OTLPSpanExporter(
            endpoint = self.url, 
            insecure = self.insecure,
            headers = self.headers or None,
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        self._has_init_runtime = True



class TemporalTelemetrySettings(BaseSettings):
    """
    Temporal Settings for Telemetry
    """

    @eproperty
    def prometheus(self) -> TemporalPrometheusSettings:
        """
        Returns the Prometheus Settings
        """
        return TemporalPrometheusSettings()
    
    @eproperty
    def otel(self) -> TemporalOTELSettings:
        """
        Returns the OTEL Settings
        """
        return TemporalOTELSettings()

    def update(self, data: t.Dict[str, t.Dict[str, t.Any]]):
        """
        Updates the data
        """
        for key, value in data.items():
            if key in {'prometheus', 'prom'}:
                self.prometheus.update(value)
                continue
            if key in {'otel', 'opentelemetry'}:
                self.otel.update(value)
                continue
    
    def get_telemetry_config(
        self, 
        provider: t.Optional[str] = None,
        init_kwargs: t.Optional[t.Dict[str, t.Any]] = None,
        config_kwargs: t.Optional[t.Dict[str, t.Any]] = None,
        init_interceptor: t.Optional[bool] = None,
        **kwargs
    ) -> t.Optional['TelemetryConfig'] | t.Optional[t.Union['Interceptor', t.Type['Interceptor']]]: 
        """
        Returns the Telemetry Runtime
        """
        if provider and provider.lower() in {'prometheus', 'prom'}:
            telm = self.prometheus
        elif provider and provider.lower() in {'otel', 'opentelemetry'}:
            telm = self.otel
        elif self.otel.enabled: telm = self.otel
        elif self.prometheus.is_enabled: telm = self.prometheus
        else: telm = None
        if telm is None: return None, None
        telm.init_runtime(**(init_kwargs or {}))
        return temporal_runtime.TelemetryConfig(
            metrics = telm.get_config(**(config_kwargs or {})),
            **kwargs,
        ), telm.get_interceptor(init = init_interceptor)