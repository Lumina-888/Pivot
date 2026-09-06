import type { ReactNode } from "react";

export function Table({
  caption,
  headers,
  children,
  empty,
}: {
  caption: string;
  headers: ReactNode[];
  children?: ReactNode;
  empty?: ReactNode;
}) {
  return (
    <div className="table-wrap">
      <table>
        <caption>{caption}</caption>
        <thead>
          <tr>
            {headers.map((header, index) => (
              <th key={index} scope="col">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {children ?? (
            <tr>
              <td colSpan={headers.length}>{empty ?? "暂无数据"}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
