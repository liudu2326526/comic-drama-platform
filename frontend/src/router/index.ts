/* frontend/src/router/index.ts */
import { createRouter, createWebHistory } from "vue-router";

const ProjectListView = () => import("@/views/ProjectListView.vue");
const ProjectCreateView = () => import("@/views/ProjectCreateView.vue");
const WorkbenchView = () => import("@/views/WorkbenchView.vue");

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/projects" },
    { path: "/projects", name: "project-list", component: ProjectListView },
    { path: "/projects/new", name: "project-new", component: ProjectCreateView },
    { path: "/projects/:id", name: "workbench", component: WorkbenchView, props: true }
  ]
});

export default router;
