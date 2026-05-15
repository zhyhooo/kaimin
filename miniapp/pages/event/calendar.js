const app = getApp()
Page({
  data: {
    year: 0, month: 0,
    days: [],
    events: [],
    eventMap: {},
    selectedDate: '',
    dateEvents: []
  },
  onLoad() {
    const now = new Date()
    this.setData({ year: now.getFullYear(), month: now.getMonth() + 1 })
    this.buildCalendar()
    this.loadEvents()
  },
  prevMonth() {
    let { year, month } = this.data
    month--
    if (month < 1) { month = 12; year-- }
    this.setData({ year, month })
    this.buildCalendar()
    this.loadEvents()
  },
  nextMonth() {
    let { year, month } = this.data
    month++
    if (month > 12) { month = 1; year++ }
    this.setData({ year, month })
    this.buildCalendar()
    this.loadEvents()
  },
  buildCalendar() {
    const { year, month } = this.data
    const firstDay = new Date(year, month - 1, 1)
    const lastDay = new Date(year, month, 0)
    const startWeekDay = firstDay.getDay()
    const totalDays = lastDay.getDate()

    let days = []
    // 填充上月尾
    const prevLast = new Date(year, month - 1, 0).getDate()
    for (let i = startWeekDay - 1; i >= 0; i--) {
      days.push({ day: prevLast - i, type: 'prev', date: `${year}-${String(month - 1 || 12).padStart(2, '0')}-${String(prevLast - i).padStart(2, '0')}` })
    }
    // 本月
    for (let i = 1; i <= totalDays; i++) {
      const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(i).padStart(2, '0')}`
      days.push({ day: i, type: 'curr', date: dateStr })
    }
    // 填充下月头
    const remaining = 7 - (days.length % 7)
    if (remaining < 7) {
      for (let i = 1; i <= remaining; i++) {
        const nm = month + 1 > 12 ? 1 : month + 1
        const ny = month + 1 > 12 ? year + 1 : year
        days.push({ day: i, type: 'next', date: `${ny}-${String(nm).padStart(2, '0')}-${String(i).padStart(2, '0')}` })
      }
    }
    this.setData({ days })
  },
  async loadEvents() {
    try {
      const res = await app.request({ url: '/events/' })
      const events = res || []
      // 建立日期 -> 事件列表映射
      const eventMap = {}
      events.forEach(e => {
        if (e.event_time) {
          const dateKey = e.event_time.split('T')[0] || e.event_time.split(' ')[0]
          if (!eventMap[dateKey]) eventMap[dateKey] = []
          eventMap[dateKey].push(e)
        }
      })
      this.setData({ events, eventMap })
    } catch (e) {}
  },
  onDateTap(e) {
    const date = e.currentTarget.dataset.date
    const dateEvents = this.data.eventMap[date] || []
    this.setData({ selectedDate: date, dateEvents })
  },
  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/event/detail?id=${id}` })
  }
})