import { motion, useReducedMotion } from "motion/react";
import "./RollingNumber.css";

const EASE = [0.2, 0.8, 0.2, 1] as const;
const DIGITS = "0123456789";

/** Odometer: each digit rolls into place. Non-digit characters (%, comma, $) render statically.
 *  The real value is in a visually hidden span so screen readers and text queries read it plainly. */
export function RollingNumber({ text }: { text: string }) {
  const reduce = useReducedMotion();
  const chars = [...text];
  return (
    <span className="roll">
      <span className="visually-hidden">{text}</span>
      <span className="roll-digits" aria-hidden="true">
        {chars.map((ch, i) => {
          const d = DIGITS.indexOf(ch);
          if (d < 0) {
            return (
              <span key={i} className="roll-static">
                {ch}
              </span>
            );
          }
          return (
            <span key={i} className="roll-col">
              <span className="roll-sizer">{ch}</span>
              <motion.span
                className="roll-stack"
                initial={reduce ? false : { y: "0em" }}
                animate={{ y: `${-d * 1}em` }}
                transition={{ duration: 0.26, ease: EASE, delay: (chars.length - i) * 0.03 }}
              >
                {DIGITS.split("").map((x) => (
                  <span key={x} className="roll-digit">
                    {x}
                  </span>
                ))}
              </motion.span>
            </span>
          );
        })}
      </span>
    </span>
  );
}
