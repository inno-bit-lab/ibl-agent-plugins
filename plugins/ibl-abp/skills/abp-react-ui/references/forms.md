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
      <SelectTrigger><SelectValue /></SelectTrigger>
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

## Showing error messages

The `errors` object is `form.formState.errors`:

```tsx
<div className="grid gap-2">
  <Label>{t('Name')}</Label>
  <Input {...form.register('name')} />
  {form.formState.errors.name && (
    <p className="text-sm text-destructive">
      {form.formState.errors.name.message}
    </p>
  )}
</div>
```

For ergonomics, extract a `<Field>` helper at the bottom of the page:

```tsx
function Field({
  label, error, children,
}: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      {children}
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  )
}

// usage:
<Field label={t('Name')} error={form.formState.errors.name?.message}>
  <Input {...form.register('name')} />
</Field>
```

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

## Edit mode — reset with existing values

```tsx
const openEdit = (entity: EntityDto) => {
  setEditing(entity)
  form.reset({
    name: entity.name,
    taxId: entity.taxId ?? '',          // wire null → form '' (Zod accepts both)
    fiscalCode: entity.fiscalCode ?? '',
    countryCode: entity.countryCode,
    segment: entity.segment,
  })
  setIsFormOpen(true)
}
```

`form.reset()` is the right way to repopulate. Setting individual fields
with `form.setValue` is for incremental updates, not initial load.

## Common pitfalls

| Symptom | Cause |
|---|---|
| Form data has `"15.50"` instead of `15.50` | Missing `valueAsNumber: true` on the register call |
| Select shows "Select…" placeholder despite a defaultValue | RHF gave the value back as `undefined`; check that the `defaultValues` matches the `name` exactly |
| Validation passes but submit doesn't fire | `<form>` is missing `onSubmit={form.handleSubmit(onSubmit)}` |
| Date input rejects existing value on edit | `form.reset({ publishedAt: dto.publishedAt?.slice(0, 10) })` — `<input type="date">` wants `YYYY-MM-DD` only |
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
