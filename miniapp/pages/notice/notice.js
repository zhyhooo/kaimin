const app = getApp()

Page({
  data: { notices: [], loading: true },
  onShow() { this.load() },
  async load() {
    this.setData({ loading: true })
    try {
      const res = await app.request({ url: '/notifications/' })
      this.setData({ notices: res || [], loading: false })
    } catch (e) { this.setData({ loading: false }) }
  },
  goDetail(e) {
    wx.navigateTo({ url: `/pages/notice/detail?id=${e.currentTarget.dataset.id}` })
  }
})
