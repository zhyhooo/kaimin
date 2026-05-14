const app = getApp()
Page({
  data: { records: [] },
  onLoad() { this.load() },
  async load() {
    const mid = app.globalData.memberId || 1
    try { const res = await app.request({ url: `/scoring/candidate/${mid}/records` }); this.setData({ records: res || [] }) } catch (e) {}
  }
})
