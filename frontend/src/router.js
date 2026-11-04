import { createRouter, createWebHistory } from 'vue-router'
import Home from './views/Home.vue'
import History from './views/History.vue'
import HistoryDetail from './views/HistoryDetail.vue'

const routes = [
  { path: '/', name: 'home', component: Home },
  { path: '/history', name: 'history', component: History },
  { path: '/history/:id', name: 'history-detail', component: HistoryDetail },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
