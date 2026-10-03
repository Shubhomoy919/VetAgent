import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef } from "react";
import { useSvtgPage } from "../../api/runs";

const EASE = [0.2, 0.8, 0.2, 1] as const;

/** Side drawer showing the indexed SVTG text for one PDF page. */
export function PassageDrawer({ page, onClose }: { page: number | null; onClose: () => void }) {
  const { data, error, isPending } = useSvtgPage(page);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (page === null) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [page, onClose]);

  return (
    <AnimatePresence>
      {page !== null && (
        <>
          <motion.div
            className="drawer-scrim"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.16 }}
            onClick={onClose}
          />
          <motion.aside
            className="drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="drawer-title"
            initial={{ x: 24, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 24, opacity: 0 }}
            transition={{ duration: 0.22, ease: EASE }}
            data-testid="passage-drawer"
          >
            <header className="drawer-head">
              <div>
                <span className="eyebrow">SVTG 2024 · source passage</span>
                <h2 id="drawer-title" className="serif drawer-title">
                  PDF page {page}
                  {data?.printed_page ? <span className="drawer-printed mono"> printed p.{data.printed_page}</span> : null}
                </h2>
              </div>
              <button ref={closeRef} type="button" className="icon-button" onClick={onClose} aria-label="Close passage">
                ×
              </button>
            </header>
            <div className="drawer-body">
              {isPending && <p className="empty-body">Loading page…</p>}
              {error && (
                <p className="error-text" role="alert">
                  {error.message}
                </p>
              )}
              {data?.chunks.map((c) => (
                <section key={c.chunk_id} className="drawer-chunk">
                  {c.section && <h3 className="eyebrow">{c.section}</h3>}
                  <p>{c.text}</p>
                </section>
              ))}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
