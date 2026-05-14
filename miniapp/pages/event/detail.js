const app = getApp()
Page({
  data: { detail: null, myReg: null },
  onLoad(opts) { this.load(opts.id) },
  async load(id) {
    try { const res = await app.request({ url: `/events/${id}` }); this.setData({ detail: res, myReg: res.my_registration }) } catch (e) {}
  },
  async signup() {
    const d = this.data.detail
    try { await app.request({ url: `/events/${d.id}/signup`, method: 'POST' }); wx.showToast({ title: '报名成功' }); this.load(d.id) } catch (e) {}
  },
  async cancel() {
    const d = this.data.detail
    try { await app.request({ url: `/events/${d.id}/cancel`, method: 'POST' }); wx.showToast({ title: '已取消' }); this.load(d.id) } catch (e) {}
  },
  async leave() {
    const d = this.data.detail
    wx.showModal({ title: '请假原因', editable: true, success: async (res) => {
      if (res.confirm) {
        try { await app.request({ url: `/events/${d.id}/leave?reason=${res.content}`, method: 'POST' }); wx.showToast({ title: '请假提交成功' }); this.load(d.id) } catch (e) {}
      }
    }})
  }
})
