import { ArrowRight, MonitorUp } from 'lucide-react';

export function Mt5BotPage() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="max-w-md rounded-lg border border-white/[0.08] bg-white/[0.02] p-8 text-center">
        <MonitorUp className="mx-auto h-12 w-12 text-tnvs-muted/40" />
        <h3 className="mt-4 text-lg font-semibold text-white">Streamlit fue descontinuado</h3>
        <p className="mt-2 text-sm text-tnvs-muted">
          Todas las funciones del dashboard Streamlit ahora están disponibles
          directamente en la aplicación React. Usá las secciones de MT5 en el menú lateral.
        </p>
        <a
          href="/mt5-dashboard"
          className="mt-6 inline-flex items-center gap-2 rounded-md bg-tnvs-purple px-4 py-2 text-sm font-medium text-white hover:bg-tnvs-purple/80"
        >
          Ir al Dashboard MT5
          <ArrowRight className="h-4 w-4" />
        </a>
      </div>
    </div>
  );
}
