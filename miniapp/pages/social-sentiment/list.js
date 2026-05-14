const app = getApp()
Page({ data: { list: [] }, onShow() { this.load() }, async load() { try { const res = await app.request({ url: '/social-info/my' }); this.setData({ list: res || [] }) } catch (e) {} } })
