import { SearchView } from "../../../../features/user/components/SearchView";

export default function SearchPage({
  searchParams,
}: {
  searchParams: { q?: string | string[] };
}) {
  const query = Array.isArray(searchParams.q) ? searchParams.q[0] : searchParams.q;
  return <SearchView initialQuery={query ?? ""} />;
}
