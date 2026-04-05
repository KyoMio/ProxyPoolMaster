import { describe, expect, it } from 'vitest'

import router from './index'

const routeNames = ['dashboard', 'proxies', 'collectors', 'logs', 'config', 'system'] as const

describe('router', () => {
  it('lazy loads each named view route', () => {
    const routes = router.options.routes.filter((route) => routeNames.includes(route.name as (typeof routeNames)[number]))

    expect(routes.map((route) => route.name)).toEqual(routeNames)

    for (const route of routes) {
      expect(typeof route.component).toBe('function')
      expect(String(route.component)).toContain('/src/views/')
    }
  })
})
