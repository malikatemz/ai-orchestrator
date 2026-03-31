import { useState, useEffect } from 'react'

export default function Home() {
  const [workflows, setWorkflows] = useState([])
  const [selectedWorkflow, setSelectedWorkflow] = useState(null)
  const [tasks, setTasks] = useState([])
  const [newWorkflow, setNewWorkflow] = useState({ name: '', description: '' })
  const [newTask, setNewTask] = useState({ name: '', input: '' })

  const fetchWorkflows = () => {
    fetch('http://localhost:8000/workflows')
      .then(res => res.json())
      .then(data => setWorkflows(data.workflows))
  }

  const fetchTasks = (workflowId) => {
    fetch(`http://localhost:8000/workflows/${workflowId}/tasks`)
      .then(res => res.json())
      .then(data => setTasks(data.tasks))
  }

  useEffect(() => {
    fetchWorkflows()
  }, [])

  const handleCreateWorkflow = () => {
    fetch('http://localhost:8000/workflows', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newWorkflow)
    }).then(() => {
      fetchWorkflows()
      setNewWorkflow({ name: '', description: '' })
    })
  }

  const handleCreateTask = () => {
    if (!selectedWorkflow) return
    fetch(`http://localhost:8000/workflows/${selectedWorkflow}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newTask)
    }).then(() => {
      fetchTasks(selectedWorkflow)
      setNewTask({ name: '', input: '' })
    })
  }

  const selectWorkflow = (id) => {
    setSelectedWorkflow(id)
    fetchTasks(id)
  }

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">AI Orchestrator Dashboard</h1>

      <div className="mb-8">
        <h2 className="text-xl mb-2">Create Workflow</h2>
        <input
          type="text"
          placeholder="Name"
          value={newWorkflow.name}
          onChange={e => setNewWorkflow({ ...newWorkflow, name: e.target.value })}
          className="border p-2 mr-2"
        />
        <input
          type="text"
          placeholder="Description"
          value={newWorkflow.description}
          onChange={e => setNewWorkflow({ ...newWorkflow, description: e.target.value })}
          className="border p-2 mr-2"
        />
        <button onClick={handleCreateWorkflow} className="bg-blue-500 text-white p-2">Create</button>
      </div>

      <div className="mb-8">
        <h2 className="text-xl mb-2">Workflows</h2>
        <ul>
          {workflows.map(wf => (
            <li key={wf.id} className="cursor-pointer p-2 border mb-2" onClick={() => selectWorkflow(wf.id)}>
              {wf.name}: {wf.description}
            </li>
          ))}
        </ul>
      </div>

      {selectedWorkflow && (
        <div>
          <h2 className="text-xl mb-2">Tasks for Workflow {selectedWorkflow}</h2>
          <div className="mb-4">
            <input
              type="text"
              placeholder="Task Name"
              value={newTask.name}
              onChange={e => setNewTask({ ...newTask, name: e.target.value })}
              className="border p-2 mr-2"
            />
            <input
              type="text"
              placeholder="Input Data"
              value={newTask.input}
              onChange={e => setNewTask({ ...newTask, input: e.target.value })}
              className="border p-2 mr-2"
            />
            <button onClick={handleCreateTask} className="bg-green-500 text-white p-2">Create Task</button>
          </div>
          <ul>
            {tasks.map(task => (
              <li key={task.id} className="p-2 border mb-2">
                {task.name} - Status: {task.status} - Retries: {task.retries} - Output: {task.output}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}