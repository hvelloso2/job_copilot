import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { HighlightedText } from './job/HighlightedText'
import { LinesField } from './profile/fields'

describe('HighlightedText', () => {
  it('marks unsupported claims in red with the reason, and placeholders in yellow', () => {
    render(
      <HighlightedText
        value="Uso Python. [[SEM SUPORTE: Tenho 3 anos de Docker]] [PREENCHER: seu nome]"
        claims={[
          { claim: 'Tenho 3 anos de Docker', evidence: null, supported: false, reason: 'Não está no perfil: 3, Docker.', start: 12, end: 34 },
        ]}
      />,
    )

    const unsupported = screen.getByText('Tenho 3 anos de Docker')
    expect(unsupported).toHaveAttribute('data-kind', 'unsupported')
    expect(unsupported).toHaveAttribute('title', 'Sem suporte no perfil. Não está no perfil: 3, Docker.')
    expect(screen.getByText('[PREENCHER: seu nome]')).toHaveAttribute('data-kind', 'placeholder')
    expect(screen.getByText('Uso Python.', { exact: false }).tagName).toBe('SPAN')
  })
})

describe('LinesField', () => {
  function Harness() {
    const [items, setItems] = useState<string[]>(['Python'])
    return (
      <>
        <LinesField label="Skills" value={items} onChange={setItems} />
        <output>{JSON.stringify(items)}</output>
      </>
    )
  }

  it('edits a list one item per line, keeping items that contain commas', async () => {
    render(<Harness />)
    const field = screen.getByLabelText('Skills')

    await userEvent.type(field, '{Enter}scikit-learn (Regressão Linear, Random Forest)')

    expect(field).toHaveValue('Python\nscikit-learn (Regressão Linear, Random Forest)')
    expect(screen.getByRole('status')).toHaveTextContent('["Python","scikit-learn (Regressão Linear, Random Forest)"]')
  })
})
