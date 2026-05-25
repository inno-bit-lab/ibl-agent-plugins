# Forms with React Hook Form + Zod

Standard form stack in this project: **React Hook Form** for state +
controlled bindings, **Zod** for schema validation, `@hookform/resolvers/zod`
to bridge them. shadcn/ui for the actual inputs.

## Why this stack

- RHF is uncontrolled-by-default → no re-render per keystroke. Forms
  with 20+ fields stay responsive.
- Zod schemas double as the source of truth for the form type:
  `z.infer<typeof schema>` gives you `FormData`.
- The same Zod schema can be shared with manual validation elsewhere
  (e.g. URL params, imports).

## Schema patterns

```ts
import { z } from 'zod'

const schema = z.object({
  // required string
  name: z.string().min(1, 'Required').max(256),

  // optional string — accept empty string from <Input>, normalize later
  taxId: z.string().max(64).optional().or(z.literal('')),

  // exact length, optional
  fiscalCode: z.string().length(16, '16 chars').optional().or(z.literal('')),

  // required, exact length
  countryCode: z.string().length(2, '2 chars'),

  // enum from a string union — matches the wire format
  segment: z.enum(['Smb', 'Enterprise', 'Public']),

  // number with min/max
  price: z.number().min(0).max(1_000_000),

  // optional number
  quantity: z.number().int().positive().optional(),

  // date as ISO string (good for <input type="date">)
  publishedAt: z.string().min(1, 'Required'),

  // boolean
  isActive: z.boolean(),

  // nested object
  address: z.object({
    street: z.string().min(1),
    city: z.string().min(1),
    zip: z.string().regex(/^\d{5}$/, 'ZIP must be 5 digits'),
  }),
})

type FormData = z.infer<typeof schema>
```

## Hooking up RHF

```tsx
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'

const form = useForm<FormData>({
  resolver: zodResolver(schema),
  defaultValues: {
    name: '',
    taxId: '',
    fiscalCode: '',
    countryCode: 'IT',
    segment: 'Smb',
    price: 0,
    publishedAt: '',
    isActive: true,
  },
})
```

## Input bindings

Three flavors depending on whether the component is "native" (forwards
ref) or "wrapped" (needs Controller).

### Native inputs (`<Input>`, `<Textarea>`) — use `register`

```tsx
<Input {...form.register('name')} />
<Input type="number" {...form.register('price', { valueAsNumber: true })} />
<Input type="date" {...form.register('publishedAt')} />
```

`valueAsNumber: true` is critical for numeric fields — otherwise the
value comes back as a string and Zod rejects it.

### Wrapped components (`<Select>`, `<DatePicker>`, custom) — use `Controller`

```tsx
<Controller
  name="segment"
  control={form.control}
  render={({ field }) => (
    <Select value={field.value} onValueChange={field.onChange}>
      <SelectTrigger className="h-10 bg-bg-elev border-0">
        <SelectValue placeholder={t('Segment', 'Segmento')} />
      </SelectTrigger>
      <SelectContent>
        {segmentOptions.map((o) => (
          <SelectItem key={o.value} value={o.value}>{t(o.key)}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  )}
/>
```

`Controller` is the bridge between RHF's uncontrolled model and the
controlled API of shadcn's Radix-based components.

Three things to get right on Radix `<Select>` specifically:

1. **Always pass `placeholder` to `<SelectValue>`** — bare
   `<SelectValue />` shows a non-translated default. Match the field
   label or write a short cue.
2. **Initialise `useForm` with the right enum value from the start**
   via the remount-on-id pattern (next section). Don't rely on
   `form.reset()` to populate a `<Controller>`-bound Select after the
   form has mounted — the hidden `<select>` and trigger text routinely
   fail to sync, leaving you with the placeholder over correct backend
   data. This is the single most common form bug we've shipped.
3. If you need to allow "no selection" semantically, keep a sentinel
   item with `value="__none__"` and map it to `undefined`/`null` in
   `onValueChange` — Radix forbids an empty-string value.

### Checkbox / Switch

```tsx
<Controller
  name="isActive"
  control={form.control}
  render={({ field }) => (
    <Checkbox checked={field.value} onCheckedChange={field.onChange} />
  )}
/>
```

## Showing error messages — use the shared `<Field>`

The project ships a shared `<Field>` primitive at
`@/components/ui/field.tsx`. **Always import it** — don't redeclare a
local `Field` function at the bottom of the page. We've already paid for
six copies of the same component, that's enough.

```tsx
import { Field } from '@/components/ui/field'

<Field
  label={t('LegalName', 'Ragione sociale')}
  required
  error={form.formState.errors.legalName?.message}
>
  <Input {...form.register('legalName')} />
</Field>
```

`<Field>` renders the label with the project's small-caps treatment
(uppercase + 0.06em tracking + `text-fg-muted`), the required asterisk in
`text-error`, the children (your input), and the error message below in
`text-xs text-error`. The signature is:

```ts
interface FieldProps {
  label: string
  required?: boolean
  error?: string
  className?: string  // extra classes on the wrapping div
  children: React.ReactNode
}
```

If you find yourself building a Label + asterisk + error block inline,
stop — that's `<Field>`.

## Submitting

```tsx
<form onSubmit={form.handleSubmit(onSubmit)}>
  {/* fields */}
  <Button type="submit" disabled={createMutation.isPending}>
    {t('AbpAccount::Save')}
  </Button>
</form>

function onSubmit(values: FormData) {
  // Optionally normalize empty strings → null at the wire boundary
  const input: CreateUpdateXxxDto = {
    name: values.name,
    taxId: values.taxId || null,        // '' → null
    fiscalCode: values.fiscalCode || null,
    countryCode: values.countryCode.toUpperCase(),
    segment: values.segment,
  }
  createMutation.mutate(input)
}
```

`handleSubmit` only calls `onSubmit` when validation passes. If
validation fails, it sets `formState.errors` and re-renders to show
messages.

## Edit mode — the remount-on-id pattern (mandatory)

**Do NOT** call `useForm` once at the top of an edit-shell and then try
to `form.reset()` the values when the entity arrives. That pattern looks
fine for plain `<Input>` fields but **silently corrupts every
`<Controller>`-wrapped Radix Select**: the hidden `<select>` keeps its
initial first-option value, the trigger renders the placeholder, and the
user sees an empty dropdown over correct backend data. We've shipped and
reverted that bug three times in this codebase.

The canonical pattern instead: **thin outer wrapper that loads the
entity, then renders a child component keyed on the id**. The child owns
`useForm` and initialises `defaultValues` directly from the loaded
entity. When the user navigates to a different entity, the key changes
→ React unmounts and remounts the child → `useForm` re-initialises from
scratch. No `useEffect`, no `reset()`, no stale Controllers.

### For an edit PAGE

```tsx
// Outer: route params + data load + remount key.
export function CustomerEditPage() {
  const { t } = useTranslation()
  const params = useParams({ strict: false }) as { id?: string }
  const id = params.id

  const { data: existing, isLoading } = useQuery({
    queryKey: ['customer', id],
    queryFn: () => getCustomer(id!),
    enabled: !!id,
  })

  if (id && isLoading) {
    return (
      <Card className="px-5 py-8 text-center text-sm text-fg-muted">
        {t('AbpAccount::PleaseWait', 'Attendere…')}
      </Card>
    )
  }

  return (
    <CustomerEditForm
      key={existing?.id ?? 'new'}
      id={id}
      existing={existing ?? null}
    />
  )
}

// Inner: useForm with the right defaults from the start.
function CustomerEditForm({
  id,
  existing,
}: { id: string | undefined; existing: CustomerDto | null }) {
  const form = useForm<CustomerFormData>({
    resolver: zodResolver(customerSchema),
    defaultValues: existing ? fromDto(existing) : defaultValues(),
  })
  // …mutations, onSubmit, JSX — no useEffect/reset.
}
```

### For an edit DIALOG

```tsx
export function ContactFormDialog({ open, onOpenChange, contact, ...rest }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        {/* Body is keyed on contact?.id so switching contacts forces a
            fresh remount. useForm then re-initialises from the current
            contact, side-stepping the stale-Controller class of bugs. */}
        {open && (
          <ContactFormBody
            key={contact?.id ?? 'new'}
            contact={contact}
            onOpenChange={onOpenChange}
            {...rest}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function ContactFormBody({ contact, ... }) {
  const form = useForm<ContactFormData>({
    resolver: zodResolver(contactSchema),
    defaultValues: contact
      ? { firstName: contact.firstName, /* …all fields, including selects… */ }
      : defaultFormValues(),
  })
  // …
}
```

### Why this matters specifically with `<Controller>` + Radix Select

When `useForm` initialises with default `role: 'Other'`, the `<Controller
name="role">` renders the Select with `value="Other"`. Radix Select wires
this through to a hidden `<select>` and to its internal `SelectValue`
text resolver. When you later call `form.reset({ role: 'Ceo' })`, RHF
updates `field.value` for the Controller — but Radix doesn't always
propagate that to the hidden `<select>` or to the trigger's displayed
text, because its `SelectContent` collection of items may not have
re-registered after the form change. Result: hidden `<select>` stuck at
`"Cfo"` (the first option), trigger showing the placeholder.

The remount-on-id pattern avoids the whole class because `useForm` never
sees the wrong value. The Select mounts already pointing at `'Ceo'`,
Radix registers items normally, and `<SelectValue />` works exactly as
documented.

### When you legitimately need `form.reset()`

After a successful submit, to clear the form back to defaults for the
next entry. Or for partial updates where the user explicitly hits
"discard changes". These are imperative, in-place operations on the
already-mounted form — they don't have the stale-Controller problem.

## Common pitfalls

| Symptom | Cause |
|---|---|
| Form data has `"15.50"` instead of `15.50` | Missing `valueAsNumber: true` on the register call |
| **Select shows the placeholder on edit, hidden `<select>` value is the first option** | Classic stale-Controller bug. You're using `useForm + useEffect + form.reset(fromDto(...))` on a Radix Select via `<Controller>`. **Fix: switch to the remount-on-id pattern above.** Don't band-aid with explicit `<span>{t(\`Enum:...\${field.value}\`)}</span>` inside the trigger — it papers over the real issue and leaves the hidden `<select>` wrong. |
| Select shows "Select…" placeholder despite a defaultValue (create mode) | RHF gave the value back as `undefined`; check that the `defaultValues` matches the `name` exactly |
| Validation passes but submit doesn't fire | `<form>` is missing `onSubmit={form.handleSubmit(onSubmit)}` |
| Date input rejects existing value on edit | Slice the ISO to `YYYY-MM-DD` in `fromDto()` — `<input type="date">` doesn't accept a full ISO with time |
| Zod error "Required" on optional field | Missing `.optional().or(z.literal(''))` — `optional()` alone doesn't accept empty strings |
| Field renders but `register` doesn't bind | Using `register` on a shadcn Radix component — switch to `<Controller>` |

## Server-side validation errors

ABP returns 400 with a structured body:

```json
{ "error": { "validationErrors": [{ "members": ["LegalName"], "message": "..." }] } }
```

Surface them per-field via `form.setError`:

```ts
mutation.mutate(input, {
  onError: (err: unknown) => {
    const e = err as { response?: { data?: { error?: { validationErrors?: Array<{ members?: string[]; message: string }> } } } }
    const ve = e?.response?.data?.error?.validationErrors
    if (Array.isArray(ve)) {
      for (const { members, message } of ve) {
        for (const m of members ?? []) {
          form.setError(m as keyof FormData, { type: 'server', message })
        }
      }
      return
    }
    toast.error(t('AbpUi::Error'))
  },
})
```

Don't try to be exhaustive — most projects accept "client validates with
Zod, server returns generic 500/400 toast" as good enough. Only wire the
per-field server errors when business rules can fail server-side in ways
the client can't predict (uniqueness, cross-record checks, etc.).
