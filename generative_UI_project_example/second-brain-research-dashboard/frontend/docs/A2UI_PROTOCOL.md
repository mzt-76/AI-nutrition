# A2UI Protocol Specification

## Overview

The A2UI (AI-to-UI) protocol is a standardized specification for representing UI components in a serializable, type-safe format. It enables AI agents to generate dynamic user interfaces by emitting structured component specifications that can be rendered by the frontend.

## Core Principles

1. **Serializable**: All component data must be JSON-serializable
2. **Type-Safe**: Components have well-defined types and props
3. **Composable**: Components can be nested to create complex UIs
4. **Extensible**: New component types can be registered in the catalog
5. **Validated**: Components are validated against the protocol before rendering

## Component Structure

### Required Fields

Every A2UI component MUST include these fields:

```typescript
interface A2UIComponent {
  id: string;        // Unique identifier
  type: string;      // Component type (e.g., "a2ui.StatCard")
  props: object;     // Component properties
}
```

#### `id` (required)
- Type: `string`
- Purpose: Unique identifier for the component
- Requirements:
  - Must be unique across the entire component tree
  - Used for React keys and component tracking
  - Should be descriptive and human-readable
- Examples: `"stat-users"`, `"headline-1"`, `"section-overview"`

#### `type` (required)
- Type: `string`
- Purpose: Specifies which React component to render
- Format: `a2ui.<ComponentName>`
- Requirements:
  - Must start with `a2ui.` prefix
  - Must be registered in the component catalog
  - Case-sensitive
- Examples: `"a2ui.StatCard"`, `"a2ui.HeadlineCard"`, `"a2ui.Section"`

#### `props` (required)
- Type: `object`
- Purpose: Properties passed to the component
- Requirements:
  - Must be a plain object (not array or primitive)
  - All values must be serializable (no functions, undefined, or symbols)
  - Null values are allowed
  - Props are component-specific
- Examples:
  ```typescript
  // StatCard props
  { label: "Users", value: "1234", trend: "+12%" }

  // HeadlineCard props
  { title: "News", summary: "Description", source: "CNN" }
  ```

### Optional Fields

Components MAY include these optional fields:

```typescript
interface A2UIComponent {
  // ... required fields
  children?: A2UIComponent[];  // Nested components
  layout?: LayoutConfig;       // Layout configuration
  styling?: StylingConfig;     // Styling configuration
}
```

#### `children` (optional)
- Type: `A2UIComponent[]`
- Purpose: Nested child components
- Requirements:
  - Must be an array
  - Each child must be a valid A2UIComponent
  - No circular references allowed
  - Maximum nesting depth: 10 (configurable)
- Example:
  ```typescript
  {
    id: "section-1",
    type: "a2ui.Section",
    props: { title: "Overview" },
    children: [
      { id: "stat-1", type: "a2ui.StatCard", props: {...} },
      { id: "stat-2", type: "a2ui.StatCard", props: {...} }
    ]
  }
  ```

#### `layout` (optional)
- Type: `object`
- Purpose: Layout and positioning configuration
- Fields:
  ```typescript
  {
    width?: string;      // CSS width (e.g., "100%", "300px")
    height?: string;     // CSS height
    position?: "relative" | "absolute" | "fixed" | "sticky";
    className?: string;  // Additional CSS classes
  }
  ```
- Example:
  ```typescript
  {
    layout: {
      width: "50%",
      position: "relative",
      className: "custom-wrapper"
    }
  }
  ```

#### `styling` (optional)
- Type: `object`
- Purpose: Styling and theming configuration
- Fields:
  ```typescript
  {
    variant?: string;    // Component variant (e.g., "primary", "secondary")
    theme?: string;      // Theme name (e.g., "dark", "light")
    className?: string;  // Additional CSS classes
  }
  ```
- Example:
  ```typescript
  {
    styling: {
      variant: "primary",
      theme: "dark",
      className: "custom-style"
    }
  }
  ```

## Validation Rules

### 1. Required Field Validation

All components MUST have `id`, `type`, and `props`:

```typescript
// Valid
{
  id: "stat-1",
  type: "a2ui.StatCard",
  props: { label: "Users", value: "100" }
}

// Invalid - missing type
{
  id: "stat-1",
  props: { label: "Users", value: "100" }
}
```

### 2. Type Validation

Component types MUST:
- Start with `a2ui.` prefix
- Be registered in the component catalog
- Be strings

```typescript
// Valid
type: "a2ui.StatCard"

// Warning - doesn't follow convention
type: "custom.Card"

// Error - not registered
type: "a2ui.NonExistentComponent"
```

### 3. Props Serialization

Props MUST be JSON-serializable:

```typescript
// Valid props
{
  label: "Users",
  value: 1234,
  active: true,
  tags: ["admin", "verified"],
  meta: { created: "2024-01-01" },
  nullable: null
}

// Invalid - contains function
{
  label: "Users",
  onClick: () => {}  // ❌ Functions not allowed
}

// Invalid - contains undefined
{
  label: "Users",
  value: undefined  // ❌ Undefined not allowed
}
```

### 4. Children Validation

If present, `children` MUST be:
- An array
- Contain valid A2UIComponent objects
- Not create circular references
- Not exceed maximum depth

```typescript
// Valid
{
  id: "parent",
  type: "a2ui.Section",
  props: {},
  children: [
    { id: "child-1", type: "a2ui.StatCard", props: {...} }
  ]
}

// Invalid - children is not an array
{
  id: "parent",
  type: "a2ui.Section",
  props: {},
  children: "invalid"  // ❌ Must be array
}
```

### 5. Unique IDs

All component IDs MUST be unique within the component tree:

```typescript
// Invalid - duplicate IDs
{
  id: "parent",
  type: "a2ui.Section",
  props: {},
  children: [
    { id: "child", type: "a2ui.StatCard", props: {...} },
    { id: "child", type: "a2ui.StatCard", props: {...} }  // ❌ Duplicate ID
  ]
}
```

### 6. Layout Validation

If present, `layout.position` MUST be one of:
- `"relative"`
- `"absolute"`
- `"fixed"`
- `"sticky"`

```typescript
// Valid
layout: { position: "relative" }

// Invalid
layout: { position: "invalid" }  // ❌ Invalid position value
```

## Component Catalog

### Registered Component Types

The following component types are currently registered:

#### News Components
- `a2ui.HeadlineCard` - News headline with summary
- `a2ui.TrendIndicator` - Trending topic indicator
- `a2ui.TimelineEvent` - Timeline event item
- `a2ui.NewsTicker` - Scrolling news ticker

#### People Components
- `a2ui.ProfileCard` - Person profile card
- `a2ui.CompanyCard` - Company/organization card
- `a2ui.QuoteCard` - Quote with attribution
- `a2ui.ExpertTip` - Expert tip callout

#### Summary Components
- `a2ui.TLDR` - Too long; didn't read summary
- `a2ui.KeyTakeaways` - Key points list
- `a2ui.ExecutiveSummary` - Executive summary
- `a2ui.TableOfContents` - Table of contents

#### Data Components
- `a2ui.StatCard` - Single statistic display
- `a2ui.MetricRow` - Multiple metrics in a row
- `a2ui.ProgressRing` - Circular progress indicator
- `a2ui.ComparisonBar` - Horizontal comparison bar
- `a2ui.DataTable` - Sortable data table
- `a2ui.MiniChart` - Small inline chart

#### Media Components
- `a2ui.VideoCard` - Video embed card
- `a2ui.ImageCard` - Image with caption
- `a2ui.PlaylistCard` - Video/audio playlist
- `a2ui.PodcastCard` - Podcast episode card

#### List Components
- `a2ui.RankedItem` - Numbered list item
- `a2ui.ChecklistItem` - Checkbox list item
- `a2ui.ProConItem` - Pro/con list item
- `a2ui.BulletPoint` - Bullet point item

#### Resource Components
- `a2ui.LinkCard` - External link card
- `a2ui.ToolCard` - Tool/software card
- `a2ui.BookCard` - Book recommendation card
- `a2ui.RepoCard` - GitHub repository card

#### Comparison Components
- `a2ui.ComparisonTable` - Comparison table
- `a2ui.VsCard` - A vs B comparison
- `a2ui.FeatureMatrix` - Feature comparison matrix
- `a2ui.PricingTable` - Pricing comparison table

#### Instructional Components
- `a2ui.StepCard` - Step-by-step instruction
- `a2ui.CodeBlock` - Code snippet with syntax highlighting
- `a2ui.CalloutCard` - Important callout box
- `a2ui.CommandCard` - CLI command display

#### Layout Components
- `a2ui.Section` - Content section container
- `a2ui.Grid` - CSS Grid layout
- `a2ui.Columns` - Multi-column layout
- `a2ui.Tabs` - Tabbed content
- `a2ui.Accordion` - Collapsible sections
- `a2ui.Carousel` - Image/content carousel
- `a2ui.Sidebar` - Sidebar layout

#### Tag Components
- `a2ui.Tag` - Simple tag/label
- `a2ui.Badge` - Badge with icon
- `a2ui.CategoryTag` - Category label
- `a2ui.StatusIndicator` - Status indicator
- `a2ui.PriorityBadge` - Priority badge
- `a2ui.TagCloud` - Tag cloud
- `a2ui.CategoryBadge` - Category badge
- `a2ui.DifficultyBadge` - Difficulty badge

## Examples

### Simple Component

```typescript
{
  id: "stat-users",
  type: "a2ui.StatCard",
  props: {
    label: "Total Users",
    value: "1,234",
    trend: "+12%",
    icon: "👤"
  }
}
```

### Component with Children

```typescript
{
  id: "overview-section",
  type: "a2ui.Section",
  props: {
    title: "Overview"
  },
  children: [
    {
      id: "stat-users",
      type: "a2ui.StatCard",
      props: { label: "Users", value: "1,234" }
    },
    {
      id: "stat-sessions",
      type: "a2ui.StatCard",
      props: { label: "Sessions", value: "5,678" }
    }
  ]
}
```

### Component with Layout and Styling

```typescript
{
  id: "headline-featured",
  type: "a2ui.HeadlineCard",
  props: {
    title: "Breaking News: A2UI Protocol Released",
    summary: "The new A2UI protocol enables AI agents to generate dynamic UIs.",
    source: "Tech News",
    published_at: "2024-01-01T12:00:00Z",
    sentiment: "positive"
  },
  layout: {
    width: "100%",
    className: "featured-card"
  },
  styling: {
    variant: "primary",
    theme: "dark"
  }
}
```

### Complex Nested Structure

```typescript
{
  id: "dashboard",
  type: "a2ui.Grid",
  props: {
    columns: 2,
    gap: "md"
  },
  children: [
    {
      id: "stats-section",
      type: "a2ui.Section",
      props: { title: "Key Metrics" },
      children: [
        { id: "stat-1", type: "a2ui.StatCard", props: {...} },
        { id: "stat-2", type: "a2ui.StatCard", props: {...} }
      ]
    },
    {
      id: "news-section",
      type: "a2ui.Section",
      props: { title: "Latest News" },
      children: [
        { id: "headline-1", type: "a2ui.HeadlineCard", props: {...} },
        { id: "headline-2", type: "a2ui.HeadlineCard", props: {...} }
      ]
    }
  ]
}
```

## Validation API

### Validate Single Component

```typescript
import { validateA2UIComponent } from '@/utils/a2ui-validator';

const component = {
  id: "test",
  type: "a2ui.StatCard",
  props: { label: "Test", value: "123" }
};

const result = validateA2UIComponent(component);

if (result.valid) {
  console.log('Component is valid!');
} else {
  console.error('Validation errors:', result.errors);
}
```

### Validate Multiple Components

```typescript
import { validateA2UIComponents } from '@/utils/a2ui-validator';

const components = [
  { id: "comp-1", type: "a2ui.StatCard", props: {...} },
  { id: "comp-2", type: "a2ui.HeadlineCard", props: {...} }
];

const result = validateA2UIComponents(components);

console.log('Valid:', result.valid);
console.log('Stats:', result.stats);
console.log('Errors:', result.errors);
console.log('Warnings:', result.warnings);
```

### Validation Options

```typescript
const result = validateA2UIComponent(component, {
  checkRegistration: true,    // Check if type is registered
  maxDepth: 10,              // Maximum nesting depth
  allowUnregistered: false,  // Treat unregistered types as warnings
  checkCircular: true,       // Check for circular references
  strict: false              // Strict mode
});
```

### Quick Validation

```typescript
import { isValidA2UIComponent } from '@/utils/a2ui-validator';

if (isValidA2UIComponent(component)) {
  // Render component
}
```

### Format Validation Results

```typescript
import { formatValidationResult } from '@/utils/a2ui-validator';

const result = validateA2UIComponent(component);
const formatted = formatValidationResult(result);

console.log(formatted);
// === A2UI Validation Result ===
// Status: ✓ VALID
// Total Components: 1
// Unique Types: 1
// Max Depth: 0
// Total Props: 2
```

## Best Practices

### 1. Use Descriptive IDs

```typescript
// Good
id: "stat-total-users"
id: "headline-breaking-news"
id: "section-overview"

// Bad
id: "s1"
id: "component-1"
id: "abc123"
```

### 2. Keep Props Flat and Simple

```typescript
// Good
props: {
  title: "News",
  summary: "Summary",
  published_at: "2024-01-01T12:00:00Z"
}

// Avoid deeply nested objects
props: {
  meta: {
    data: {
      nested: {
        value: "too deep"
      }
    }
  }
}
```

### 3. Validate Early

```typescript
// Validate before sending to frontend
const components = generateComponents();
const result = validateA2UIComponents(components);

if (!result.valid) {
  console.error('Invalid components:', result.errors);
  return;
}

// Send to frontend
sendToFrontend(components);
```

### 4. Use Type-Specific Props

Each component type has its own expected props. Refer to the component's TypeScript interface for the exact prop structure.

### 5. Avoid Deep Nesting

Keep component trees shallow for better performance and maintainability:

```typescript
// Good - max 2-3 levels
Section -> Grid -> StatCard

// Avoid - excessive nesting
Section -> Container -> Wrapper -> Box -> Grid -> Column -> Card -> ...
```

## Error Handling

### Missing Component Type

If a component type is not registered in the catalog, the renderer will display an error card:

```typescript
{
  id: "unknown",
  type: "a2ui.UnknownComponent",  // Not registered
  props: {}
}
// Renders: Yellow warning card with component details
```

### Invalid Component Structure

Invalid components will be caught during validation:

```typescript
{
  id: "invalid",
  type: "a2ui.StatCard",
  props: {
    onClick: () => {}  // ❌ Not serializable
  }
}
// Validation Error: NON_SERIALIZABLE_PROP
```

## Extending the Protocol

### Registering New Components

To add a new component type to the catalog:

1. Create the React component in `/frontend/src/components/A2UI/[Category]/`
2. Register it in `/frontend/src/lib/a2ui-catalog.tsx`:

```typescript
export const a2uiCatalog: Record<string, ComponentRenderer> = {
  // ... existing components
  "a2ui.NewComponent": (props: any) => <NewComponent {...props} />,
};
```

3. Update the TypeScript types if needed
4. Validate that existing components still work

## Version History

- **v1.0** - Initial protocol specification
  - Core component structure (id, type, props)
  - Optional children, layout, styling
  - Validation rules
  - 45+ component types registered

## References

- Component Catalog: `/frontend/src/lib/a2ui-catalog.tsx`
- Validator: `/frontend/src/utils/a2ui-validator.ts`
- Renderer: `/frontend/src/components/A2UIRenderer.tsx`
- Tests: `/frontend/src/utils/__tests__/a2ui-validator.test.ts`
