import { ChevronLeft, ChevronRight } from "lucide-react";
import { buttonClasses } from "./tokens";

// Pagination — compact page controls with ellipsis for large page counts.
// Client-side only (operates on an already-loaded/filtered/sorted array's
// length); reuses the same chip-active treatment already established by
// the Dashboard's filter chips, and the shared Button hierarchy for
// Previous/Next.

/** Below this many total pages, every page number is shown — no ellipsis
 * needed. Above it, only the current page's neighbors plus the first/last
 * page are shown, with "…" collapsing the gap. */
const ELLIPSIS_THRESHOLD = 7;

export function getPaginationRange(
  current: number,
  totalPages: number,
  siblingCount = 1,
): (number | "ellipsis")[] {
  if (totalPages <= ELLIPSIS_THRESHOLD) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const leftSibling = Math.max(current - siblingCount, 1);
  const rightSibling = Math.min(current + siblingCount, totalPages);
  const showLeftEllipsis = leftSibling > 2;
  const showRightEllipsis = rightSibling < totalPages - 1;

  const pages: (number | "ellipsis")[] = [1];
  if (showLeftEllipsis) pages.push("ellipsis");
  for (let p = Math.max(leftSibling, 2); p <= Math.min(rightSibling, totalPages - 1); p++) {
    pages.push(p);
  }
  if (showRightEllipsis) pages.push("ellipsis");
  pages.push(totalPages);
  return pages;
}

export function Pagination({
  page,
  pageSize,
  totalItems,
  onPageChange,
  itemLabel = "items",
}: {
  page: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  itemLabel?: string;
}) {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  if (totalPages <= 1) return null;

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, totalItems);
  const pages = getPaginationRange(page, totalPages);

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-3 mt-4">
      <p className="text-xs text-gray-500">
        Showing {start}–{end} of {totalItems} {itemLabel}
      </p>
      <nav className="flex items-center gap-1.5" aria-label="Pagination">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page === 1}
          className={buttonClasses("secondary", "sm")}
          aria-label="Previous page"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
          Previous
        </button>

        {pages.map((p, i) =>
          p === "ellipsis" ? (
            <span key={`ellipsis-${i}`} className="px-1.5 text-gray-600 text-xs select-none">
              …
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p)}
              aria-current={p === page ? "page" : undefined}
              className={`min-w-[28px] px-2 py-1.5 rounded-md text-xs font-medium transition-colors ${
                p === page
                  ? "bg-blue-600 text-white"
                  : "bg-gray-900 text-gray-400 border border-gray-800 hover:text-gray-200 hover:border-gray-700"
              }`}
            >
              {p}
            </button>
          ),
        )}

        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page === totalPages}
          className={buttonClasses("secondary", "sm")}
          aria-label="Next page"
        >
          Next
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </nav>
    </div>
  );
}
