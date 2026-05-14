const app = getApp()
Page({
  data: { events: [] },
  onShow() { this.load() },
  async load() {
    try { const res = await app.request({ url: '/events/' }); this.setData({ events: res || [] }) } catch (e) {}
  },
  goDetail(e) { wx.navigateTo({ url: `/pages/event/detail?id=${e.currentTarget.dataset.id}` }) }
})
