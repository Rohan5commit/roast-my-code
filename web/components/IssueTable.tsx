"use client";

import { useState, useMemo } from "react";

export interface Issue {
  file: string;
  line: number | null;
  category: string;
  severity: "high" | "medium" | "low";
  description: string;
}

interface IssueTableProps {
  issues: Issue[];
}

export default function IssueTable({ issues }: IssueTableProps) {
  const [sortBy, setSortBy] = useState<"severity" | "file" | "category">("severity");
  const [filterSeverity, setFilterSeverity] = useState<string>("all");
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [search, setSearch] = useState("");

  const severityOrder = { high: 0, medium: 1, low: 2 };

  const categories = useMemo(() => [...new Set(issues.map((i) => i.category))], [issues]);

  const filtered = useMemo(() =>
    issues
      .filter((i) => filterSeverity === "all" || i.severity === filterSeverity)
      .filter((i) => filterCategory === "all" || i.category === filterCategory)
      .filter(
        (i) =>
          search === "" ||
          i.description.toLowerCase().includes(search.toLowerCase()) ||
          i.file.toLowerCase().includes(search.toLowerCase())
      )
      .sort((a, b) => {
        if (sortBy === "severity") return severityOrder[a.severity] - severityOrder[b.severity];
        if (sortBy === "file") return a.file.localeCompare(b.file);
        return a.category.localeCompare(b.category);
      }),
    [issues, filterSeverity, filterCategory, search, sortBy]
  );

  const severityColor = {
    high: "bg-red-500/20 text-red-400",
    medium: "bg-yellow-500/20 text-yellow-400",
    low: "bg-blue-500/20 text-blue-400",
  };

  return (
    <div>
      <div className="flex flex-wrap gap-3 mb-4">
        <div>
          <label htmlFor="issue-search" className="sr-only">Search issues</label>
          <input
            id="issue-search"
            type="text"
            placeholder="Search issues..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="px-4 py-2 bg-roast-bg border border-roast-border rounded-lg text-roast-text placeholder-roast-muted focus:outline-none focus:border-roast-accent"
          />
        </div>
        <div>
          <label htmlFor="severity-filter" className="sr-only">Filter by severity</label>
          <select
            id="severity-filter"
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            className="px-4 py-2 bg-roast-bg border border-roast-border rounded-lg text-roast-text focus:outline-none focus:border-roast-accent"
          >
            <option value="all">All Severities</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
        <div>
          <label htmlFor="category-filter" className="sr-only">Filter by category</label>
          <select
            id="category-filter"
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            className="px-4 py-2 bg-roast-bg border border-roast-border rounded-lg text-roast-text focus:outline-none focus:border-roast-accent"
          >
            <option value="all">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="sort-by" className="sr-only">Sort by</label>
          <select
            id="sort-by"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as "severity" | "file" | "category")}
            className="px-4 py-2 bg-roast-bg border border-roast-border rounded-lg text-roast-text focus:outline-none focus:border-roast-accent"
          >
            <option value="severity">Sort by Severity</option>
            <option value="file">Sort by File</option>
            <option value="category">Sort by Category</option>
          </select>
        </div>
      </div>

      <p className="text-sm text-roast-muted mb-3" aria-live="polite">{filtered.length} issues found</p>

      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <caption className="sr-only">Code issues found during analysis</caption>
          <thead>
            <tr className="border-b border-roast-border">
              <th scope="col" className="pb-3 text-roast-muted font-medium">Severity</th>
              <th scope="col" className="pb-3 text-roast-muted font-medium">File</th>
              <th scope="col" className="pb-3 text-roast-muted font-medium">Line</th>
              <th scope="col" className="pb-3 text-roast-muted font-medium">Category</th>
              <th scope="col" className="pb-3 text-roast-muted font-medium">Description</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((issue, i) => (
              <tr key={`${issue.file}-${issue.line}-${i}`} className="border-b border-roast-border/50 hover:bg-roast-card/50">
                <td className="py-3">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${severityColor[issue.severity]}`}>
                    {issue.severity}
                  </span>
                </td>
                <td className="py-3 text-roast-text font-mono text-sm">{issue.file}</td>
                <td className="py-3 text-roast-muted">{issue.line ?? "-"}</td>
                <td className="py-3 text-roast-muted">{issue.category}</td>
                <td className="py-3 text-roast-text text-sm">{issue.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-8 text-roast-muted" role="status">
          No issues match your filters. Nice code!
        </div>
      )}
    </div>
  );
}
