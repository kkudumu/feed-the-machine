import type { Page, Locator } from "playwright";

export interface RefEntry {
  role: string;
  name: string;
  nth: number;
  // Locator strategy for reliable resolution
  locatorType: "role" | "label" | "placeholder" | "name-attr" | "text" | "nth-selector";
  locatorValue: string;
  locatorSelector?: string; // CSS selector fallback
}

export interface SnapshotNode {
  ref?: string;
  role: string;
  name: string;
  interactive: boolean;
  tagName?: string;
  type?: string;
  value?: string;
  href?: string;
  children?: SnapshotNode[];
  checked?: boolean;
  disabled?: boolean;
  level?: number;
}

export interface SnapshotResult {
  tree: SnapshotNode | null;
  refs: Record<string, RefEntry>;
  /** Raw Playwright ARIA text snapshot */
  aria_text?: string;
}

// Map from HTML tag/role to canonical ARIA role
const TAG_TO_ROLE: Record<string, string> = {
  a: "link",
  button: "button",
  input: "textbox",
  textarea: "textbox",
  select: "combobox",
  h1: "heading",
  h2: "heading",
  h3: "heading",
  h4: "heading",
  h5: "heading",
  h6: "heading",
  img: "img",
  nav: "navigation",
  main: "main",
  header: "banner",
  footer: "contentinfo",
  aside: "complementary",
  section: "region",
  article: "article",
  form: "form",
  table: "table",
  ul: "list",
  ol: "list",
  li: "listitem",
  p: "paragraph",
};

const INPUT_TYPE_TO_ROLE: Record<string, string> = {
  checkbox: "checkbox",
  radio: "radio",
  button: "button",
  submit: "button",
  reset: "button",
  range: "slider",
  number: "spinbutton",
  search: "searchbox",
  text: "textbox",
  email: "textbox",
  password: "textbox",
  tel: "textbox",
  url: "textbox",
};

const INTERACTIVE_ROLES = new Set([
  "button",
  "link",
  "textbox",
  "searchbox",
  "combobox",
  "checkbox",
  "radio",
  "switch",
  "slider",
  "spinbutton",
  "menuitem",
  "menuitemcheckbox",
  "menuitemradio",
  "tab",
  "treeitem",
  "option",
]);

let refMap: Map<string, RefEntry> = new Map();
let refCounter = 0;

// Track how many times each (locatorType, locatorValue) pair appears for nth
const locatorCounts: Map<string, number> = new Map();

export function resetRefs(): void {
  refMap = new Map();
  refCounter = 0;
  locatorCounts.clear();
}

export function getRefMap(): Map<string, RefEntry> {
  return refMap;
}

function getLocatorNth(key: string): number {
  const nth = locatorCounts.get(key) ?? 0;
  locatorCounts.set(key, nth + 1);
  return nth;
}

function assignRef(entry: Omit<RefEntry, "ref">): string {
  refCounter++;
  const ref = `@e${refCounter}`;
  refMap.set(ref, entry);
  return ref;
}

interface RawElement {
  tagName: string;
  role: string;
  ariaRole: string | null;
  accessibleName: string;
  inputType: string | null;
  inputName: string | null;
  inputId: string | null;
  inputPlaceholder: string | null;
  value: string | null;
  href: string | null;
  checked: boolean | null;
  disabled: boolean | null;
  level: number | null;
  labelText: string | null;
  // CSS selector for positional fallback
  positionSelector: string;
  selectorIndex: number;
}

export async function buildSnapshot(
  page: Page,
  interactiveOnly: boolean = false
): Promise<SnapshotResult> {
  resetRefs();

  // Get aria text from _snapshotForAI if available (best effort)
  let aria_text: string | undefined;
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const snapResult = await (page as any)._snapshotForAI({});
    if (snapResult?.full) {
      // Sanitize: remove control characters that would break JSON encoding
      aria_text = (snapResult.full as string).replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, "");
    }
  } catch {
    // Not available in all Playwright versions
  }

  // Build structured element list from DOM
  const rawElements = await page.evaluate((interactiveOnly: boolean) => {
    const INTERACTIVE_SELECTORS = [
      "a[href]",
      "button",
      "input:not([type='hidden'])",
      "select",
      "textarea",
      "[role='button']",
      "[role='link']",
      "[role='textbox']",
      "[role='combobox']",
      "[role='checkbox']",
      "[role='radio']",
      "[role='tab']",
      "[role='menuitem']",
      "[role='option']",
      "[role='switch']",
      "[role='slider']",
      "[tabindex]:not([tabindex='-1'])",
    ];

    const CONTENT_SELECTORS = [
      "h1", "h2", "h3", "h4", "h5", "h6",
      "p", "main", "nav", "header", "footer",
      "article", "section", "form",
    ];

    const selector = interactiveOnly
      ? INTERACTIVE_SELECTORS.join(",")
      : [...INTERACTIVE_SELECTORS, ...CONTENT_SELECTORS].join(",");

    const seen = new Set<Element>();

    // Count elements by selector for nth positioning
    const selectorCounts: Record<string, number> = {};

    return Array.from(document.querySelectorAll(selector))
      .filter(el => {
        if (seen.has(el)) return false;
        seen.add(el);
        return true;
      })
      .map(el => {
        const htmlEl = el as HTMLElement;
        const tagName = htmlEl.tagName.toLowerCase();
        const explicitRole = htmlEl.getAttribute("role") || null;
        const inputType = tagName === "input"
          ? (htmlEl as HTMLInputElement).type?.toLowerCase() || "text"
          : null;

        // Build accessible name using priority chain
        const ariaLabel = htmlEl.getAttribute("aria-label") || null;
        const ariaLabelledBy = htmlEl.getAttribute("aria-labelledby") || null;
        const inputId = htmlEl.id || null;
        const inputName = (htmlEl as HTMLInputElement).name || null;
        const inputPlaceholder = (htmlEl as HTMLInputElement).placeholder || null;

        let labelText: string | null = null;
        // Check for label[for=id]
        if (inputId) {
          const label = document.querySelector(`label[for="${inputId}"]`);
          labelText = label?.textContent?.trim() || null;
        }
        // Check for wrapping label
        if (!labelText) {
          const parentLabel = htmlEl.closest("label");
          if (parentLabel) {
            // Get label text without input's own text
            const clone = parentLabel.cloneNode(true) as HTMLElement;
            clone.querySelectorAll("input, select, textarea").forEach(i => i.remove());
            labelText = clone.textContent?.trim() || null;
          }
        }
        // aria-labelledby lookup
        let ariaLabelledByText: string | null = null;
        if (ariaLabelledBy) {
          const labelEl = document.getElementById(ariaLabelledBy);
          ariaLabelledByText = labelEl?.textContent?.trim() || null;
        }

        const accessibleName = ariaLabel || ariaLabelledByText || labelText
          || (tagName !== "input" && tagName !== "select" && tagName !== "textarea"
            ? htmlEl.textContent?.trim().substring(0, 150) || ""
            : null)
          || inputPlaceholder
          || inputName
          || "";

        // Level for headings
        const headingMatch = tagName.match(/^h([1-6])$/);
        const level = headingMatch ? parseInt(headingMatch[1], 10) : null;

        // Position selector for nth fallback
        const posSelector = tagName + (inputType && tagName === "input" ? `[type="${inputType}"]` : "")
          + (inputName ? `[name="${inputName}"]` : "");
        selectorCounts[posSelector] = (selectorCounts[posSelector] || 0) + 1;
        const selectorIndex = selectorCounts[posSelector] - 1;

        return {
          tagName,
          role: tagName,
          ariaRole: explicitRole,
          accessibleName,
          inputType,
          inputName,
          inputId,
          inputPlaceholder,
          value: (tagName === "input" || tagName === "textarea")
            ? (htmlEl as HTMLInputElement).value || null
            : null,
          href: tagName === "a" ? (htmlEl as HTMLAnchorElement).href || null : null,
          checked: (inputType === "checkbox" || inputType === "radio")
            ? (htmlEl as HTMLInputElement).checked : null,
          disabled: htmlEl.hasAttribute("disabled")
            ? true
            : htmlEl.getAttribute("aria-disabled") === "true"
            ? true
            : null,
          level,
          labelText,
          positionSelector: posSelector,
          selectorIndex,
        } as RawElement;
      });
  }, interactiveOnly);

  // Convert raw elements to snapshot nodes with refs
  const nodes: SnapshotNode[] = rawElements.map(
    (el: RawElement): SnapshotNode => {
      // Compute canonical role
      let role: string;
      if (el.ariaRole) {
        role = el.ariaRole;
      } else if (el.tagName === "input" && el.inputType) {
        role = INPUT_TYPE_TO_ROLE[el.inputType] || "textbox";
      } else {
        role = TAG_TO_ROLE[el.tagName] || el.tagName;
      }

      const isInteractive = INTERACTIVE_ROLES.has(role.toLowerCase());

      const node: SnapshotNode = {
        role,
        name: el.accessibleName,
        interactive: isInteractive,
        tagName: el.tagName,
      };

      if (el.inputType) node.type = el.inputType;
      if (el.value !== null) node.value = el.value;
      if (el.href !== null) node.href = el.href;
      if (el.checked !== null) node.checked = el.checked;
      if (el.disabled !== null) node.disabled = el.disabled;
      if (el.level !== null) node.level = el.level;

      // Assign ref to interactive elements
      if (isInteractive) {
        // Choose best locator strategy
        let locatorType: RefEntry["locatorType"];
        let locatorValue: string;

        const accessibleName = el.accessibleName;

        if (el.labelText && el.labelText.trim()) {
          // Has a proper label — use getByLabel
          locatorType = "label";
          locatorValue = el.labelText.trim();
        } else if (el.ariaRole && accessibleName) {
          // Explicit role with name — use getByRole
          locatorType = "role";
          locatorValue = accessibleName;
        } else if (el.tagName === "a" && accessibleName) {
          // Link with text — use role=link
          locatorType = "role";
          locatorValue = accessibleName;
        } else if (el.tagName === "button" && accessibleName) {
          // Button with text — use role=button
          locatorType = "role";
          locatorValue = accessibleName;
        } else if (el.inputPlaceholder) {
          // Input with placeholder
          locatorType = "placeholder";
          locatorValue = el.inputPlaceholder;
        } else if (el.inputName) {
          // Input with name attribute — CSS selector approach
          locatorType = "name-attr";
          locatorValue = el.inputName;
        } else if (accessibleName) {
          // Fallback: text content
          locatorType = "text";
          locatorValue = accessibleName;
        } else {
          // Last resort: nth CSS selector
          locatorType = "nth-selector";
          locatorValue = el.positionSelector;
        }

        const locKey = `${locatorType}::${locatorValue}`;
        const nth = getLocatorNth(locKey);

        node.ref = assignRef({
          role,
          name: accessibleName,
          nth,
          locatorType,
          locatorValue,
          locatorSelector: el.positionSelector,
        });
      }

      return node;
    }
  );

  const tree: SnapshotNode = {
    role: "document",
    name: "",
    interactive: false,
    children: nodes,
  };

  const refs: Record<string, RefEntry> = {};
  for (const [key, value] of refMap.entries()) {
    refs[key] = value;
  }

  return { tree, refs, aria_text };
}

export function resolveRef(page: Page, ref: string): Locator {
  const entry = refMap.get(ref);
  if (!entry) {
    throw new Error(
      `Ref ${ref} not found. The page may have changed — please re-snapshot.`
    );
  }

  const { role, locatorType, locatorValue, locatorSelector, nth } = entry;

  switch (locatorType) {
    case "label":
      return page.getByLabel(locatorValue, { exact: false }).nth(nth);

    case "placeholder":
      return page.getByPlaceholder(locatorValue, { exact: false }).nth(nth);

    case "name-attr":
      // CSS selector by name attribute
      if (locatorSelector) {
        return page.locator(`${locatorSelector}`).nth(nth);
      }
      return page.locator(`[name="${locatorValue}"]`).nth(nth);

    case "role": {
      const playwrightRole = getPlaywrightRole(role);
      if (playwrightRole) {
        return page
          .getByRole(playwrightRole as Parameters<typeof page.getByRole>[0], {
            name: locatorValue || undefined,
          })
          .nth(nth);
      }
      // Fallback
      return page.getByText(locatorValue, { exact: false }).nth(nth);
    }

    case "text":
      return page.getByText(locatorValue, { exact: false }).nth(nth);

    case "nth-selector":
      return page.locator(locatorValue).nth(nth);

    default:
      throw new Error(`Unknown locator type for ref ${ref}`);
  }
}

function getPlaywrightRole(role: string): string | null {
  const roleMap: Record<string, string> = {
    link: "link",
    button: "button",
    textbox: "textbox",
    searchbox: "searchbox",
    combobox: "combobox",
    checkbox: "checkbox",
    radio: "radio",
    slider: "slider",
    spinbutton: "spinbutton",
    switch: "switch",
    tab: "tab",
    tablist: "tablist",
    tabpanel: "tabpanel",
    menuitem: "menuitem",
    menuitemcheckbox: "menuitemcheckbox",
    menuitemradio: "menuitemradio",
    option: "option",
    listbox: "listbox",
    heading: "heading",
    img: "img",
    navigation: "navigation",
    main: "main",
    banner: "banner",
    contentinfo: "contentinfo",
    complementary: "complementary",
    region: "region",
    article: "article",
    form: "form",
    table: "table",
    row: "row",
    cell: "cell",
    columnheader: "columnheader",
    rowheader: "rowheader",
    list: "list",
    listitem: "listitem",
    tree: "tree",
    treeitem: "treeitem",
    grid: "grid",
    gridcell: "gridcell",
    dialog: "dialog",
    alertdialog: "alertdialog",
    alert: "alert",
    status: "status",
    log: "log",
    progressbar: "progressbar",
    tooltip: "tooltip",
  };

  return roleMap[role.toLowerCase()] || null;
}

export async function checkRefStale(
  page: Page,
  ref: string
): Promise<{ stale: boolean; error?: string }> {
  try {
    const locator = resolveRef(page, ref);
    // ~5ms fast-fail check
    const count = await locator.count();
    if (count === 0) {
      return {
        stale: true,
        error: `Ref ${ref} no longer exists on the page. Please re-snapshot and use the new ref.`,
      };
    }
    return { stale: false };
  } catch (err) {
    return {
      stale: true,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}
