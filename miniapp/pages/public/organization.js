const app = getApp()
Page({ data: { org: null }, onLoad() { this.load() }, async load() { try { const res = await app.request({ url: '/public/organization' }); this.setData({ org: res }) } catch (e) {} } })
