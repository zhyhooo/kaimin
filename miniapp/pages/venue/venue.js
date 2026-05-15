const app = getApp()
Page({ data: { venue: null }, onLoad() { this.load() }, async load() { try { const vid = app.globalData.venueId || 1; const res = await app.request({ url: `/venues/${vid}` }); this.setData({ venue: res }) } catch (e) {} }, goBooking() { wx.navigateTo({ url: '/pages/venue/booking' }) } })
