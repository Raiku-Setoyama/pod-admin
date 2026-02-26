"use client"

import * as React from "react"
import { format } from "date-fns"
import { ja } from "date-fns/locale"
import { CalendarIcon, X } from "lucide-react"
import { DateRange } from "react-day-picker"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

interface DateRangePickerProps {
  value: DateRange | undefined
  onChange: (range: DateRange | undefined) => void
  placeholder?: string
  className?: string
}

export function DateRangePicker({
  value,
  onChange,
  placeholder = "日付で絞り込み",
  className,
}: DateRangePickerProps) {
  const [open, setOpen] = React.useState(false)
  const [tempRange, setTempRange] = React.useState<DateRange | undefined>(value)

  React.useEffect(() => {
    setTempRange(value)
  }, [value])

  const handleApply = () => {
    onChange(tempRange)
    setOpen(false)
  }

  const handleClear = () => {
    setTempRange(undefined)
    onChange(undefined)
    setOpen(false)
  }

  const handleOpenChange = (isOpen: boolean) => {
    setOpen(isOpen)
    if (isOpen) {
      setTempRange(value)
    }
  }

  const formatDateRange = (range: DateRange | undefined) => {
    if (!range) return null
    if (range.from && range.to) {
      return `${format(range.from, "yyyy/MM/dd", { locale: ja })} - ${format(range.to, "yyyy/MM/dd", { locale: ja })}`
    }
    if (range.from) {
      return `${format(range.from, "yyyy/MM/dd", { locale: ja })} -`
    }
    return null
  }

  const displayText = formatDateRange(value)

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn(
            "justify-start text-left font-normal",
            !value && "text-muted-foreground",
            className
          )}
        >
          <CalendarIcon className="mr-2 h-4 w-4" />
          {displayText || placeholder}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="range"
          defaultMonth={tempRange?.from}
          selected={tempRange}
          onSelect={setTempRange}
          numberOfMonths={2}
        />
        <div className="flex items-center justify-end gap-2 border-t p-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClear}
            disabled={!tempRange?.from && !tempRange?.to}
          >
            <X className="mr-1 h-4 w-4" />
            クリア
          </Button>
          <Button
            size="sm"
            onClick={handleApply}
            disabled={!tempRange?.from}
          >
            適用
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
