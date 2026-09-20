import time
from agents import TracingProcessor, set_trace_processors, set_tracing_disabled
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

_provider = TracerProvider()
_provider.add_span_processor(
    SimpleSpanProcessor(ConsoleSpanExporter(out=open("traces.log", "a", encoding="utf-8")))
)
trace.set_tracer_provider(_provider)
tracer = trace.get_tracer("food-agent")


class OTelBridge(TracingProcessor):
    def __init__(self):
        self._otel, self._t0 = {}, {}
        self.reset()

    def reset(self):
        self.stats = {"model_calls": 0, "tool_calls": 0, "tool_seconds": {}}

    def on_trace_start(self, tr):
        self._otel[tr.trace_id] = tracer.start_span(f"run:{tr.name}")

    def on_trace_end(self, tr):
        s = self._otel.pop(tr.trace_id, None)
        if s:
            s.end()

    @staticmethod
    def _label(sp):
        d = sp.span_data
        kind = getattr(d, "type", "span")
        name = getattr(d, "name", None) or getattr(d, "model", None) or ""
        return f"{kind}:{name}" if name else str(kind)

    def on_span_start(self, sp):
        parent = self._otel.get(sp.parent_id) or self._otel.get(sp.trace_id)
        ctx = trace.set_span_in_context(parent) if parent else None
        self._otel[sp.span_id] = tracer.start_span(self._label(sp), context=ctx)
        self._t0[sp.span_id] = time.perf_counter()

    def on_span_end(self, sp):
        span = self._otel.pop(sp.span_id, None)
        took = time.perf_counter() - self._t0.pop(sp.span_id, time.perf_counter())
        d = sp.span_data
        kind = getattr(d, "type", "")
        if kind == "generation":
            self.stats["model_calls"] += 1
            usage = getattr(d, "usage", None) or {}
            if span:
                span.set_attribute("llm.input_tokens", int(usage.get("input_tokens", 0) or 0))
                span.set_attribute("llm.output_tokens", int(usage.get("output_tokens", 0) or 0))
        elif kind == "function":
            self.stats["tool_calls"] += 1
            n = getattr(d, "name", "?")
            ts = self.stats["tool_seconds"]
            ts[n] = round(ts.get(n, 0) + took, 2)
        if span:
            span.set_attribute("duration_s", round(took, 3))
            span.end()

    def shutdown(self): pass
    def force_flush(self): pass


bridge = OTelBridge()
set_tracing_disabled(False)
set_trace_processors([bridge])