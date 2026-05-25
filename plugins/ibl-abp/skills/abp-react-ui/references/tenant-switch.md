# Tenant switcher (multi-tenancy UI)

For ABP multi-tenant projects, the React app needs a way to switch
between **host** context (cross-tenant admin) and a specific **tenant**
context. The mechanism is the `__tenant` HTTP header, plus a small UI to
set it.

This is a **one-time setup per project**, not per entity. If the project
already has a TenantSwitch component in `components/layout/`, you're
done — just verify it works and move on.

## What the axios interceptor already does

`react/src/lib/api/axios.ts` exports:

```ts
export function setTenantId(tenantId: string | null): void {
  if (tenantId) sessionStorage.setItem('abp_tenant_id', tenantId)
  else          sessionStorage.removeItem('abp_tenant_id')
}
```

…and the request interceptor reads `sessionStorage['abp_tenant_id']` and,
when set, adds the `__tenant: <id>` header to every API call. So **the
switcher's only job** is to call `setTenantId(...)` and trigger a reload
so the UI picks up the new tenant's permissions, localization, and data.

## The TenantSwitch component

Pattern (already in IBL360 at
`react/src/components/layout/TenantSwitch.tsx`):

```tsx
import { useEffect, useState } from 'react'
import { Building2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from 'sonner'
import { setTenantId, api } from '@/lib/api/axios'

const ABP_TENANT_NAME_KEY = 'abp_tenant_name'   // for UI display only

interface TenantResolveResult {
  success: boolean
  tenantId?: string | null
  name?: string | null
}

export function TenantSwitch() {
  const { t } = useTranslation()
  const [open, setOpen]       = useState(false)
  const [name, setName]       = useState('')
  const [current, setCurrent] = useState<string | null>(null)
  const [busy, setBusy]       = useState(false)

  useEffect(() => {
    // Refresh display name whenever dialog opens/closes
    setCurrent(sessionStorage.getItem(ABP_TENANT_NAME_KEY))
  }, [open])

  async function applyTenant(tenantName: string) {
    setBusy(true)
    try {
      const trimmed = tenantName.trim()
      // Empty string = switch back to host
      if (!trimmed) {
        setTenantId(null)
        sessionStorage.removeItem(ABP_TENANT_NAME_KEY)
        toast.success(t('::TenantSwitchedToHost', 'Switched to host context'))
        setOpen(false)
        window.location.reload()
        return
      }

      // Resolve tenant by name (works for any user — abp/multi-tenancy
      // endpoints are unauthenticated by design)
      const { data } = await api.get<TenantResolveResult>(
        '/abp/multi-tenancy/tenants/by-name/' + encodeURIComponent(trimmed),
        { skipAuthRedirect: true, skip403Redirect: true }
      )

      if (!data?.success || !data.tenantId) {
        toast.error(t('::TenantNotFound', 'Tenant not found'))
        return
      }

      setTenantId(data.tenantId)
      sessionStorage.setItem(ABP_TENANT_NAME_KEY, data.name ?? trimmed)
      toast.success(t('::TenantSwitchedTo', 'Switched to tenant {{name}}', {
        name: data.name ?? trimmed,
      }))
      setOpen(false)
      // Full reload picks up new permissions, localization, and clears
      // React Query cache so data fetches respect the new tenant context.
      window.location.reload()
    } catch {
      toast.error(t('AbpUi::Error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        className="gap-2"
        onClick={() => {
          setName(sessionStorage.getItem(ABP_TENANT_NAME_KEY) ?? '')
          setOpen(true)
        }}
        title={t('::SwitchTenant', 'Switch tenant')}
      >
        <Building2 className="size-4" />
        <span className="hidden sm:inline">
          {current ? current : t('::Host', 'Host')}
        </span>
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('::SwitchTenant', 'Switch tenant')}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-2 py-4">
            <Label htmlFor="tenantName">
              {t('::TenantName', 'Tenant name (leave empty for host)')}
            </Label>
            <Input
              id="tenantName"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="demo"
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              {t('AbpUi::Cancel')}
            </Button>
            <Button onClick={() => void applyTenant(name)} disabled={busy}>
              {t('AbpUi::Save', 'Apply')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
```

Wire it into the header (`components/layout/Header.tsx`) next to the
language switcher:

```tsx
import { TenantSwitch } from './TenantSwitch'

// inside the right-side controls cluster:
<TenantSwitch />
<LanguageSwitcher />
<ThemeToggle />
```

## Why a full reload after switching

React Query's cache is keyed by query keys, not by tenant. Without a
reload you'd see the old tenant's data until each query naturally
revalidates. Worse, `appConfig` (permissions, localization) is cached in
memory and won't refetch automatically.

A full reload is the cleanest cut: new auth state, new permission set,
new localization, fresh data. The downsides (the user loses unsaved
form state, a brief loading screen) are acceptable for an action the
user explicitly initiated.

If you want to avoid the reload for power-user reasons, you'd need to:
1. `appConfig.clear()` and re-fetch with the new tenant header.
2. `queryClient.clear()` to drop all cached server state.
3. Re-fetch the user's permissions and rebuild route guards.

Almost never worth it.

## Single-page app caveats

- `sessionStorage` is per-tab. Opening a new tab gives a fresh host
  context — useful for "what does this look like as the host admin while
  I'm in tenant X" workflows.
- Don't put the tenant id in `localStorage` — surviving the tab close
  and applying it to all future tabs is confusing.

## When the project doesn't have multi-tenancy

If the backend's `IsMultiTenant = false`, the TenantSwitch component
just adds clutter. Skip it. Conversely, if the backend is multi-tenant
but the project only has tenant users (no host admin UI), you can still
skip the switcher and rely on each user's claim-based tenant resolution.
