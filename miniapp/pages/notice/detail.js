const app = getApp()
Page({
  data: { detail: null },
  onLoad(opts) { this.load(opts.id) },
  async load(id) {
    try { const res = await app.request({ url: `/notifications/${id}` }); this.setData({ detail: res }) } catch (e) {}
  }
})
