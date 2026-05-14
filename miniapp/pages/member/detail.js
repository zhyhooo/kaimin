const app = getApp()
Page({
  data: { member: null },
  onLoad(opts) { this.load(opts.id) },
  async load(id) { try { const res = await app.request({ url: `/members/${id}` }); this.setData({ member: res }) } catch (e) {} }
})
