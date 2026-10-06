import { Link, useLocation } from "react-router";
import { EmptySpecimen } from "../../components/EmptySpecimen";

/** 404: a specimen plate with nothing catalogued at this address. */
export function NotFoundPage() {
  const { pathname } = useLocation();
  return (
    <div className="datapage" data-testid="not-found">
      <EmptySpecimen title="Specimen not found" plate="404" testId="not-found-plate">
        <p>
          Nothing is catalogued at <span className="mono">{pathname}</span>. Specimens are kept on the Bench and in the
          case ledger.
        </p>
        <p className="plate-empty-actions">
          <Link className="btn btn-primary" to="/">
            Back to the Bench
          </Link>
          <Link className="btn" to="/cases">
            Case ledger
          </Link>
        </p>
      </EmptySpecimen>
    </div>
  );
}
