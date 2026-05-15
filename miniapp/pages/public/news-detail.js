const app = getApp()
Page({
  data: { detail: null },
  onLoad(opts) { this.load(opts.id) },
  async load(id) {
    try {
      const res = await app.request({ url: `/public/news/${id}`, noAuth: true })
      this.setData({ detail: res })
    } catch (e) {}
  }
})