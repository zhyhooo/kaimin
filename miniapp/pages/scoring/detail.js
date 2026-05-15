const app = getApp()
Page({
  data: { records: [] },
  onLoad() { this.load() },
  async load() {
    const mid = app.globalData.memberId
    if (!mid) {
      wx.showToast({ title: '请先登录', icon: 'none' })
      return
    }
    try { const res = await app.request({ url: `/scoring/candidate/${mid}/records` }); this.setData({ records: res || [] }) } catch (e) {}
  }
})
