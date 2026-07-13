import type { InsightRow } from "../api/types";

interface DataTableProps {
  rows: InsightRow[];
  rowCount: number | null;
}

export function DataTable({ rows, rowCount }: DataTableProps) {
  if (rows.length === 0) {
    return <p className="empty-state">No rows matched your request.</p>;
  }

  const columns = Object.keys(rows[0]);

  return (
    <div className="data-table">
      <h3>
        Data{" "}
        <span className="row-count">
          ({rowCount ?? rows.length} row{(rowCount ?? rows.length) === 1 ? "" : "s"})
        </span>
      </h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                {columns.map((col) => (
                  <td key={col}>{String(row[col] ?? "")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
