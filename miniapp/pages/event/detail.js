const app = getApp()
Page({
  data: { detail: null, myReg: null },
  onLoad(opts) { this.load(opts.id) },
  async load(id) {
    try {
      const [res, branchesRes] = await Promise.all([
        app.request({ url: `/events/${id}` }),
        app.request({ url: '/branches/' })
      ])
      // 解析支部名称
      const branchMap = {}
      ;(branchesRes || []).forEach(b => { branchMap[b.id] = b.name })
      res._branchName = res.branch_id ? (branchMap[res.branch_id] || '支部活动') : '全市活动'
      // 计算活动状态
      const now = new Date()
      const deadline = res.signup_deadline ? new Date(res.signup_deadline) : null
      const eventTime = res.event_time ? new Date(res.event_time) : null
      res._status = !deadline ? 'open' : (now > deadline ? 'closed' : 'open')
      res._ended = eventTime && now > eventTime
      // 报名状态
      const reg = res.my_registration
      if (reg) {
        reg._status = reg.is_leave ? 'leave' : (reg.is_checked_in ? 'checked_in' : 'registered')
      }
      this.setData({ detail: res, myReg: reg || null })
    } catch (e) {}
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
        try {
          await app.request({ url: `/events/${d.id}/leave?reason=${encodeURIComponent(res.content)}`, method: 'POST' })
          wx.showToast({ title: '请假提交成功' }); this.load(d.id)
        } catch (e) {}
      }
    }})
  }
})
