import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#050505] px-5 text-[#f4f4f4]">
      <section className="w-full max-w-2xl border border-[#404040] bg-[#0d0d0d]">
        <div className="border-b border-[#404040] bg-[#171717] px-4 py-3">
          <div className="text-[10px] font-black tracking-[0.14em] text-[#ffb000]">
            CDRR · ROUTING ERROR
          </div>
        </div>

        <div className="p-8 md:p-12">
          <div className="text-[10px] font-bold tracking-[0.16em] text-[#777]">
            HTTP 404
          </div>

          <h1 className="mt-4 text-3xl font-black tracking-tight text-[#f4f4f4]">
            MARKET SURFACE NOT FOUND
          </h1>

          <p className="mt-4 max-w-lg text-sm leading-7 text-[#999]">
            The requested CDRR route does not exist. Return to the risk radar
            or choose another terminal surface.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/dashboard"
              className="border border-[#ffb000] bg-[#ffb000] px-4 py-2 text-xs font-black text-black transition hover:bg-transparent hover:text-[#ffb000]"
            >
              RISK RADAR
            </Link>

            <Link
              href="/"
              className="border border-[#555] bg-[#111] px-4 py-2 text-xs font-bold text-[#d0d0d0] transition hover:border-[#888] hover:text-white"
            >
              HOME
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
